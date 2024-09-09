document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('questionForm');
  const resultDiv = document.getElementById('result');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = document.getElementById('questionInput').value;
    
    resultDiv.textContent = 'Analyzing...';
    
    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });
      
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      
      const data = await response.json();
      resultDiv.textContent = data.result;
    } catch (error) {
      console.error('Error:', error);
      resultDiv.textContent = 'An error occurred while processing your request.';
    }
  });
});
