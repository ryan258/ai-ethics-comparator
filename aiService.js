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

async function getModelResponse(modelName, prompt) {
  try {
    const client = getClient();
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
  } catch (error) {
    console.error('Error querying OpenRouter:', error);
    if (error.status) {
      throw new Error(`OpenRouter API error (${error.status}): ${error.message || 'Unknown error.'}`);
    }
    throw new Error('Failed to retrieve response from the AI model.');
  }
}

module.exports = { getModelResponse };
