
require('dotenv').config();
const express = require('express');
const fs = require('fs').promises;
const aiService = require('./aiService');

const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static('public'));

app.get('/api/paradoxes', async (req, res) => {
  try {
    const paradoxes = await fs.readFile('paradoxes.json', 'utf8');
    res.json(JSON.parse(paradoxes));
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Failed to read paradoxes file.' });
  }
});

app.post('/api/query', async (req, res) => {
  const { modelName, paradoxId, groups } = req.body;

  if (!modelName || !paradoxId) {
    return res.status(400).json({ error: 'Missing modelName or paradoxId in request body.' });
  }

  try {
    const paradoxesData = await fs.readFile('paradoxes.json', 'utf8');
    const paradoxes = JSON.parse(paradoxesData);
    const paradox = paradoxes.find(p => p.id === paradoxId);

    if (!paradox) {
      return res.status(404).json({ error: 'Paradox not found.' });
    }

    const prompt = buildPrompt(paradox, groups);
    const aiResponse = await aiService.getModelResponse(modelName, prompt);
    res.json({ response: aiResponse, prompt });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: error.message || 'An error occurred while processing your request.' });
  }
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});

function buildPrompt(paradox, providedGroups = {}) {
  const { promptTemplate, group1Default, group2Default } = paradox;
  if (!promptTemplate) {
    return paradox.prompt || '';
  }

  const group1Text = normalizeGroupText(providedGroups.group1, group1Default);
  const group2Text = normalizeGroupText(providedGroups.group2, group2Default);

  return promptTemplate
    .replaceAll('{{GROUP1}}', group1Text)
    .replaceAll('{{GROUP2}}', group2Text);
}

function normalizeGroupText(value, fallback) {
  const trimmed = (value || '').trim();
  if (trimmed.length === 0) {
    return fallback || '';
  }
  return trimmed;
}
