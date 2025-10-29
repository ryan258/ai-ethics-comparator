
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
  const { modelName, paradoxId } = req.body;

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

    const prompt = paradox.prompt;
    const aiResponse = await aiService.getModelResponse(modelName, prompt);
    res.json({ response: aiResponse });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'An error occurred while processing your request.' });
  }
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
