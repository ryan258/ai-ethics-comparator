const OpenAI = require('openai');

let cachedClient = null;

// Retry configuration
const MAX_RETRIES = 4; // Increased to 4 for better reliability
const INITIAL_RETRY_DELAY = 2000; // 2 seconds (increased from 1s)

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

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

async function getModelResponseWithRetry(modelName, prompt, systemPrompt = '', params = {}, retryCount = 0) {
  try {
    const client = getClient();

    // Build request parameters
    const requestParams = {
      model: modelName,
      temperature: params.temperature ?? 1.0,
      top_p: params.top_p ?? 1.0,
      max_tokens: params.max_tokens ?? 1000,
      frequency_penalty: params.frequency_penalty ?? 0,
      presence_penalty: params.presence_penalty ?? 0
    };

    // Only include seed if provided
    if (params.seed !== undefined && params.seed !== null) {
      requestParams.seed = params.seed;
    }

    let response;

    // Use chat.completions API if a system prompt is provided, otherwise use responses.create
    if (systemPrompt && systemPrompt.length > 0) {
      const messages = [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: prompt }
      ];

      try {
        response = await client.chat.completions.create({
          ...requestParams,
          messages: messages
        });
      } catch (apiError) {
        // Add more context to JSON parsing errors
        if (apiError.message && apiError.message.includes('JSON')) {
          console.error('JSON parsing error - API may have returned HTML or empty response');
          console.error('Model:', modelName);
          console.error('Retry count:', retryCount);
        }
        throw apiError;
      }

      if (response?.choices?.[0]?.message?.content) {
        return response.choices[0].message.content.trim();
      }

      return 'The model returned an empty response.';
    } else {
      // Legacy responses.create API (no system prompt)
      // Note: responses.create may not support all parameters
      try {
        response = await client.responses.create({
          model: modelName,
          input: prompt,
          // Include parameters that are supported by responses.create
          temperature: requestParams.temperature,
          max_tokens: requestParams.max_tokens
        });
      } catch (apiError) {
        // Add more context to JSON parsing errors
        if (apiError.message && apiError.message.includes('JSON')) {
          console.error('JSON parsing error - API may have returned HTML or empty response');
          console.error('Model:', modelName);
          console.error('Retry count:', retryCount);
        }
        throw apiError;
      }

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

      // Retry on 429 (rate limit) or 5xx (server errors)
      const shouldRetry = (statusCode === 429 || statusCode >= 500) && retryCount < MAX_RETRIES;

      if (shouldRetry) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount);
        console.log(`Retrying after ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
        await sleep(delay);
        return getModelResponseWithRetry(modelName, prompt, systemPrompt, params, retryCount + 1);
      }

      // Add context based on status code
      if (statusCode === 404) {
        throw new Error(`Model not found: ${errorMsg}`);
      } else if (statusCode === 429) {
        throw new Error(`Rate limit exceeded after ${MAX_RETRIES} retries: ${errorMsg}`);
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
      // Network errors are retryable
      const shouldRetry = retryCount < MAX_RETRIES;
      if (shouldRetry) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount);
        console.log(`Network error - retrying after ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
        await sleep(delay);
        return getModelResponseWithRetry(modelName, prompt, systemPrompt, params, retryCount + 1);
      }
      throw new Error(`Network error after ${MAX_RETRIES} retries (${error.code}): ${error.message || 'Connection failed'}`);
    }

    // Handle JSON parsing errors specifically
    if (error.message && error.message.includes('JSON')) {
      const shouldRetry = retryCount < MAX_RETRIES;
      if (shouldRetry) {
        const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCount);
        console.log(`JSON parsing error - retrying after ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})...`);
        await sleep(delay);
        return getModelResponseWithRetry(modelName, prompt, systemPrompt, params, retryCount + 1);
      }
      throw new Error(`API returned invalid response after ${MAX_RETRIES} retries. This may indicate rate limiting or an API outage.`);
    }

    throw new Error(`Failed to retrieve response: ${error.message || 'Unknown error'}`);
  }
}

// Public wrapper function
async function getModelResponse(modelName, prompt, systemPrompt = '', params = {}) {
  return getModelResponseWithRetry(modelName, prompt, systemPrompt, params, 0);
}

module.exports = { getModelResponse };
