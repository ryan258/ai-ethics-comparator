async function getModelResponse(modelName, prompt) {
  // In the future, this will call the actual AI model
  console.log(`Getting response from ${modelName} for prompt: "${prompt}"`);
  return `This is a dummy response from ${modelName}.`;
}

module.exports = { getModelResponse };
