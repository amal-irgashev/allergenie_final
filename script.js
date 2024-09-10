document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('questionForm');
  const resultDiv = document.getElementById('result');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = document.getElementById('questionInput').value;
    
    resultDiv.innerHTML = '<p>Analyzing...</p>';
    
    try {
      const response = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question }),
      });
      
      const responseText = await response.text();
      console.log('Raw response:', responseText);
      
      let data;
      try {
        data = JSON.parse(responseText);
      } catch (parseError) {
        console.error('JSON parse error:', parseError);
        throw new Error('Failed to parse JSON response');
      }
      
      if (!response.ok) {
        throw new Error(`${data.error}: ${data.details} (${data.type})`);
      }
      
      resultDiv.innerHTML = marked.parse(data.result);
    } catch (error) {
      console.error('Error:', error);
      resultDiv.innerHTML = `<p>An error occurred: ${error.message}</p>`;
    }
  });
});