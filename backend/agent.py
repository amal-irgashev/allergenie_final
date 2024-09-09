from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
from langchain_community.utilities import GoogleSerperAPIWrapper
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()


# 1. Function to load and vectorize PDF
def load_and_vectorize_pdf():
    file_path = "backend/allergen_doc.pdf"
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(documents, embeddings)

    return db


# 2. Function for similarity search
def retrieve_info(db, query):
    similar_docs = db.similarity_search(query, k=3)
    page_contents_array = [doc.page_content for doc in similar_docs]
    return page_contents_array


# 3. Setup LLMChain & prompts
llm = ChatOpenAI(temperature=0, model="gpt-4o")

template = """
You are Ameer's Allergen SafeGuard, an AI assistant specialized in determining product safety based on Ameer's specific allergens and triggers. Use the following context from the provided PDF to answer the question.

Ameer's Specific Allergens (Verified by Dermatologists):
- Food Allergens (IgE Test Results): Peanuts, Walnuts, Pistachios, Cashews, Hazelnuts, Macadamia Nuts, Chestnuts, Pecans, Brazil Nuts, Green Peas.
- Contact Dermatitis Triggers (Patch Test Results): Balsam of Peru, BHA (Butylated Hydroxyanisole), Dimethylaminopropylamine, Fragrance Mix, Hydroquinone, Nickel Sulfate, Octyl Gallate, Parabens.
- Environmental Allergens: Birch, Cottonwood, Dust Mites, Animal Dander, Cockroaches.

Safety Logic:
- If a product contains any of Ameer's allergens, it is not safe.
- If a product does not contain any of Ameer's allergens, it is safe.

When recommending products:
1. First, list products from the ACDS CAMP document (if applicable).
2. Then, search for additional safe products online.
3. Always provide direct links to products.
4. List out ingredients of recommended products to verify safety.

Context from PDF:
{context}

Question: {question}

Provide a concise answer focusing only on Ameer's allergens and triggers. If allergens are present, briefly list them in point form. If the product is safe, boldly highlight this. Do not discuss other sensitivities or suggest consulting medical professionals. For each part of your answer, provide a link to the web source you used for that information. If searching online, ensure you include links to all sources used.

Answer:
"""

prompt = PromptTemplate(input_variables=["context", "question"],
                        template=template)

chain = LLMChain(llm=llm, prompt=prompt)


# Function to perform web search
def web_search(query):
    search = GoogleSerperAPIWrapper()
    results = search.run(query)
    return results


# Generate answer function
def generate_answer(db, question):
    context = retrieve_info(db, question)

    # Perform web search
    web_results = web_search(question)
    context.append(f"Web search results: {web_results}")

    # Join the context list into a single string
    context_str = "\n".join(context)

    response = chain.run(context=context_str, question=question)
    return response


# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# Initialize the database
db = load_and_vectorize_pdf()


@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get('question')

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    try:
        result = generate_answer(db, question)
        return jsonify({'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Modify the main function to run the Flask app
def main():
    app.run(host='0.0.0.0', port=5001, debug=True)


if __name__ == '__main__':
    main()
