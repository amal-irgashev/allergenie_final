from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
from langchain_community.utilities import GoogleSerperAPIWrapper
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re

load_dotenv()

# Ensure you have set the SERPER_API_KEY in your .env file
serper_api_key = os.getenv("SERPER_API_KEY")
if not serper_api_key:
    raise ValueError("SERPER_API_KEY not found in environment variables")

# Initialize GoogleSerperAPIWrapper
search = GoogleSerperAPIWrapper()

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
You are Ameer's Allergen SafeGuard, an AI assistant specialized in determining product safety based on Ameer's specific allergens and triggers. Use the following context from the provided PDF and web search results to answer the question.

Ameer's Specific Allergens (Verified by Dermatologists):
- Food Allergens (IgE Test Results): Peanuts, Walnuts, Pistachios, Cashews, Hazelnuts, Macadamia Nuts, Chestnuts, Pecans, Brazil Nuts, Green Peas.
- Contact Dermatitis Triggers (Patch Test Results): Balsam of Peru, BHA (Butylated Hydroxyanisole), Dimethylaminopropylamine, Fragrance Mix, Hydroquinone, Nickel Sulfate, Octyl Gallate, Parabens.
- Environmental Allergens: Birch, Cottonwood, Dust Mites, Animal Dander, Cockroaches.

Safety Logic:
- If a product contains any of Ameer's allergens, it is not safe.
- If a product does not contain any of Ameer's allergens, it is safe.

When recommending products:
1. First, list products from the ACDS CAMP document (if applicable).
2. Then, use the web search results to find additional safe products.
3. Always provide direct links to products using the format [Product Name](URL).
4. List out ingredients of recommended products to verify safety.

Context from PDF:
{context}

Web Search Results:
{web_results}

Question: {question}

Provide a concise answer focusing only on Ameer's allergens and triggers. If allergens are present, briefly list them in point form. If the product is safe, boldly highlight this. Do not discuss other sensitivities or suggest consulting medical professionals. Use the provided web search results to support your answer and include relevant links.
ho
For each piece of information from web search results, cite the source using the format [Source](URL) at the end of the sentence or paragraph.

Answer:
"""

prompt = PromptTemplate(input_variables=["context", "web_results", "question"],
                        template=template)

chain = LLMChain(llm=llm, prompt=prompt)


# Function to perform web search
def web_search(query):
    try:
        search = GoogleSerperAPIWrapper()
        results = search.results(query)
        formatted_results = []
        for result in results.get('organic', [])[:5]:  # Increase to top 5 results
            product_info = get_product_info(result['link'], result['title'])
            if product_info['ingredients']:  # Only include results with ingredients
                formatted_results.append({
                    "title": result['title'],
                    "link": result['link'],
                    "snippet": result['snippet'],
                    "ingredients": product_info['ingredients'],
                    "is_safe": product_info['is_safe']
                })
            if len(formatted_results) >= 3:  # Stop after finding 3 results with ingredients
                break
        return formatted_results
    except Exception as e:
        print(f"Error in web search: {e}")
        return []


# Improve the get_product_info function
def get_product_info(url, title):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try different methods to find ingredients
        ingredients = find_ingredients(soup, url, title)
        
        # Check if the product is safe based on Ameer's allergens
        is_safe = is_product_safe(ingredients) if ingredients else "Unknown"
        
        return {
            "ingredients": ingredients,
            "is_safe": is_safe
        }
    except Exception as e:
        print(f"Error getting product info from {url}: {e}")
        return {"ingredients": None, "is_safe": "Unknown"}

def find_ingredients(soup, url, title):
    # Method 1: Look for common ingredient div classes or IDs
    for class_name in ['ingredients', 'product-ingredients', 'ingredient-list']:
        ingredients_element = soup.find('div', class_=re.compile(class_name, re.I))
        if ingredients_element:
            return clean_ingredients(ingredients_element.text)
    
    # Method 2: Look for ingredient headers
    headers = soup.find_all(['h2', 'h3', 'h4', 'strong'], string=re.compile(r'ingredients', re.I))
    for header in headers:
        next_element = header.find_next(['p', 'ul', 'div'])
        if next_element:
            return clean_ingredients(next_element.text)
    
    # Method 3: Search for ingredient patterns in all text
    all_text = soup.get_text()
    ingredient_match = re.search(r'ingredients:?\s*(.*)', all_text, re.I | re.S)
    if ingredient_match:
        return clean_ingredients(ingredient_match.group(1))
    
    # Method 4: If it's an e-commerce site, try to find the product page
    if is_ecommerce_site(url):
        product_url = find_product_page(soup, url, title)
        if product_url and product_url != url:
            return get_product_info(product_url, title)['ingredients']
    
    return None

def clean_ingredients(text):
    # Remove common filler words and clean up the ingredient list
    cleaned = re.sub(r'\s+', ' ', text).strip()
    cleaned = re.sub(r'^ingredients:?\s*', '', cleaned, flags=re.I)
    return cleaned

def is_ecommerce_site(url):
    ecommerce_patterns = ['amazon', 'walmart', 'target', 'ebay', 'etsy']
    return any(pattern in urlparse(url).netloc for pattern in ecommerce_patterns)

def find_product_page(soup, base_url, title):
    for link in soup.find_all('a', href=True):
        if title.lower() in link.text.lower():
            return urljoin(base_url, link['href'])
    return None

# Modify the is_product_safe function
def is_product_safe(ingredients):
    if not ingredients:
        return "Unknown"
    
    allergens = [
        "Peanuts", "Walnuts", "Pistachios", "Cashews", "Hazelnuts", "Macadamia Nuts", 
        "Chestnuts", "Pecans", "Brazil Nuts", "Green Peas", "Balsam of Peru", 
        "BHA", "Butylated Hydroxyanisole", "Dimethylaminopropylamine", "Fragrance Mix", 
        "Hydroquinone", "Nickel Sulfate", "Octyl Gallate", "Parabens"
    ]
    
    ingredients_lower = ingredients.lower()
    found_allergens = [allergen for allergen in allergens if allergen.lower() in ingredients_lower]
    
    if found_allergens:
        return f"Not safe. Contains: {', '.join(found_allergens)}"
    return "Safe"

# Modify the generate_answer function
def generate_answer(db, question):
    context = retrieve_info(db, question)
    context_str = "\n".join(context)

    web_results = web_search(question)
    web_results_str = "\n".join([
        f"Title: {result['title']}\n"
        f"Link: {result['link']}\n"
        f"Snippet: {result['snippet']}\n"
        f"Ingredients: {result['ingredients']}\n"
        f"Safety: {result['is_safe']}\n"
        for result in web_results
    ])

    try:
        response = chain.run(context=context_str, web_results=web_results_str, question=question)
        return response
    except Exception as e:
        print(f"Error generating answer: {e}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."


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
