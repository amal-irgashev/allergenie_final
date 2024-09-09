from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback
from pydantic import BaseModel, Field, field_validator
import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()

# Ensure you have set the SERPER_API_KEY in your .env file
serper_api_key = os.getenv("SERPER_API_KEY")
if not serper_api_key:
    raise ValueError("SERPER_API_KEY not found in environment variables")

# Initialize GoogleSerperAPIWrapper
search = GoogleSerperAPIWrapper()

class ProductSafety(BaseModel):
    product_name: str
    is_safe: bool
    allergens_found: List[str] = Field(default_factory=list)
    confidence_score: float
    explanation: str

    @field_validator('allergens_found')
    def check_allergens(cls, v):
        if not isinstance(v, list):
            raise ValueError('allergens_found must be a list')
        return v

    @field_validator('confidence_score')
    def check_confidence_score(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('confidence_score must be between 0 and 1')
        return v

# Function to perform web search
def web_search(query):
    try:
        results = search.results(query)
        formatted_results = []
        for result in results.get('organic', [])[:3]:  # Limit to top 3 results
            product_info = get_product_info(result['link'], result['title'])
            if product_info['ingredients']:  # Only include results with ingredients
                formatted_results.append({
                    "title": result['title'],
                    "link": result['link'],
                    "snippet": result['snippet'],
                    "ingredients": product_info['ingredients'],
                })
        return formatted_results
    except Exception as e:
        print(f"Error in web search: {e}")
        return []

def get_product_info(url, title):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        ingredients = find_ingredients(soup, url, title)
        
        return {
            "ingredients": ingredients,
        }
    except Exception as e:
        print(f"Error getting product info from {url}: {e}")
        return {"ingredients": None}

def find_ingredients(soup, url, title):
    # Look for common ingredient labels
    ingredient_labels = ['ingredients:', 'ingredients', 'what\'s inside', 'contains:']
    
    # Search for paragraphs or list items containing ingredient information
    for label in ingredient_labels:
        elements = soup.find_all(['p', 'li', 'div'], string=re.compile(label, re.IGNORECASE))
        for element in elements:
            text = element.get_text(strip=True)
            if len(text) > len(label) + 10:  # Ensure there's substantial text after the label
                return text

    # If no ingredients found with labels, try to find a list of ingredients
    lists = soup.find_all('ul')
    for ul in lists:
        items = ul.find_all('li')
        if 5 <= len(items) <= 30:  # Typical range for ingredient lists
            return ', '.join([item.get_text(strip=True) for item in items])

    # If still no ingredients found, look for a paragraph with common ingredient words
    paragraphs = soup.find_all('p')
    ingredient_words = ['water', 'sodium', 'acid', 'oil', 'extract', 'vitamin']
    for p in paragraphs:
        text = p.get_text(strip=True)
        if any(word in text.lower() for word in ingredient_words) and len(text) > 50:
            return text

    # If all else fails, return None
    return None

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

Web Search Results:
{web_results}

Question: {question}

Provide a concise answer focusing only on Ameer's allergens and triggers. If allergens are present, briefly list them in point form. If the product is safe, boldly highlight this. Do not discuss other sensitivities or suggest consulting medical professionals. Use the provided web search results to support your answer and include relevant links.

For each piece of information from web search results, cite the source using the format [Source](URL) at the end of the sentence or paragraph.

Answer:
"""

prompt = PromptTemplate(input_variables=["web_results", "question"], template=template)

# Initialize the language model
llm = ChatOpenAI(temperature=0, model="gpt-4")

# Create the chain
chain = LLMChain(llm=llm, prompt=prompt)

# Generate answer function
def generate_answer(question):
    web_results = web_search(question)
    web_results_str = "\n".join([
        f"Title: {result['title']}\n"
        f"Link: {result['link']}\n"
        f"Snippet: {result['snippet']}\n"
        f"Ingredients: {result['ingredients']}\n"
        for result in web_results
    ])

    try:
        with get_openai_callback() as cb:
            response = chain.run(web_results=web_results_str, question=question)
            print(f"Total Tokens: {cb.total_tokens}")
            print(f"Prompt Tokens: {cb.prompt_tokens}")
            print(f"Completion Tokens: {cb.completion_tokens}")
            print(f"Total Cost (USD): ${cb.total_cost}")
        return response
    except Exception as e:
        print(f"Error generating answer: {e}")
        return "I'm sorry, but I encountered an error while processing your request. Please try again later."

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get('question')
    if not question:
        return jsonify({"error": "No question provided"}), 400

    answer = generate_answer(question)
    return jsonify({"result": answer})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
