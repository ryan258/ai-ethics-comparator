const OpenAI = require('openai');

let cachedClient = null;

function getClient() {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error('OPENROUTER_API_KEY is not set in the environment.');
  }

  if (!cachedClient) {
    cachedClient = new OpenAI({
      apiKey,
      baseURL: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1',
      defaultHeaders: {
        'HTTP-Referer': process.env.APP_BASE_URL || 'http://localhost:3000',
        'X-Title': process.env.APP_NAME || 'AI Ethics Comparator'
      }
    });
  }

  return cachedClient;
}

async function getModelResponse(modelName, prompt, systemPrompt = '') {
  try {
    const client = getClient();

    // Use chat.completions API if a system prompt is provided, otherwise use responses.create
    if (systemPrompt && systemPrompt.length > 0) {
      const messages = [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: prompt }
      ];

      const response = await client.chat.completions.create({
        model: modelName,
        messages: messages
      });

      if (response?.choices?.[0]?.message?.content) {
        return response.choices[0].message.content.trim();
      }

      return 'The model returned an empty response.';
    } else {
      // Legacy responses.create API (no system prompt)
      const response = await client.responses.create({
        model: modelName,
        input: prompt
      });

      if (response?.output_text) {
        return response.output_text.trim();
      }

      if (response?.output?.length) {
        const combinedText = response.output
          .map(part => part?.content?.map(c => c?.text).join(' ').trim())
          .join('\n')
          .trim();
        if (combinedText) {
          return combinedText;
        }
      }

      return 'The model returned an empty response.';
    }
  } catch (error) {
    console.error('Error querying OpenRouter:', error);

    // Enhanced error passthrough from OpenRouter
    if (error.status) {
      const statusCode = error.status;
      let errorMsg = error.message || 'Unknown error';

      // Try to extract more detailed error information
      if (error.error) {
        if (error.error.message) {
          errorMsg = error.error.message;
        } else if (typeof error.error === 'string') {
          errorMsg = error.error;
        }
      }

      // Add context based on status code
      if (statusCode === 404) {
        throw new Error(`Model not found: ${errorMsg}`);
      } else if (statusCode === 429) {
        throw new Error(`Rate limit exceeded: ${errorMsg}`);
      } else if (statusCode === 402 || statusCode === 403) {
        throw new Error(`Billing or authentication issue: ${errorMsg}`);
      } else if (statusCode === 401) {
        throw new Error(`Invalid API key: ${errorMsg}`);
      } else {
        throw new Error(`OpenRouter API error (${statusCode}): ${errorMsg}`);
      }
    }

    // Handle network or other errors
    if (error.code) {
      throw new Error(`Network error (${error.code}): ${error.message || 'Connection failed'}`);
    }

    throw new Error(`Failed to retrieve response: ${error.message || 'Unknown error'}`);
  }
}

module.exports = { getModelResponse };
