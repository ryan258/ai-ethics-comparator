
require('dotenv').config();
const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const aiService = require('./aiService');

const RESULTS_ROOT = path.join(__dirname, 'results');

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
  const { modelName, paradoxId, groups = {}, iterations } = req.body;

  if (!modelName || !paradoxId) {
    return res.status(400).json({ error: 'Missing modelName or paradoxId in request body.' });
  }

  const iterationCount = normalizeIterationCount(iterations);

  try {
    const paradoxesData = await fs.readFile('paradoxes.json', 'utf8');
    const paradoxes = JSON.parse(paradoxesData);
    const paradox = paradoxes.find(p => p.id === paradoxId);

    if (!paradox) {
      return res.status(404).json({ error: 'Paradox not found.' });
    }

    const { prompt, group1Text, group2Text } = buildPrompt(paradox, groups);
    const responses = [];

    for (let iteration = 0; iteration < iterationCount; iteration += 1) {
      const rawResponse = await aiService.getModelResponse(modelName, prompt);
      const parsed = parseDecision(rawResponse);
      const explanationText = parsed?.explanation?.trim?.() || '';

      responses.push({
        iteration: iteration + 1,
        decisionToken: parsed?.token ?? null,
        group: parsed?.group ?? null,
        explanation: explanationText,
        raw: rawResponse,
        timestamp: new Date().toISOString()
      });
    }

    const summary = computeSummary(responses, {
      group1: group1Text,
      group2: group2Text
    });

    const { runDir, runId } = await createRunDirectory(modelName);
    const runTimestamp = new Date().toISOString();
    const runRecord = {
      runId,
      timestamp: runTimestamp,
      modelName,
      paradoxId,
      prompt,
      groups: { group1: group1Text, group2: group2Text },
      iterationCount,
      summary,
      responses
    };

    await fs.writeFile(path.join(runDir, 'run.json'), JSON.stringify(runRecord, null, 2), 'utf8');
    const persisted = JSON.parse(await fs.readFile(path.join(runDir, 'run.json'), 'utf8'));
    res.json(persisted);
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

  const group1Text = normalizeGroupText(providedGroups.group1, group1Default);
  const group2Text = normalizeGroupText(providedGroups.group2, group2Default);

  const basePrompt = promptTemplate || paradox.prompt || '';
  const prompt = basePrompt
    .replaceAll('{{GROUP1}}', group1Text)
    .replaceAll('{{GROUP2}}', group2Text);

  return { prompt, group1Text, group2Text };
}

function normalizeGroupText(value, fallback) {
  const trimmed = (value || '').trim();
  if (trimmed.length === 0) {
    return fallback || '';
  }
  return trimmed;
}

function normalizeIterationCount(value) {
  const parsed = parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  return Math.min(parsed, 50);
}

async function createRunDirectory(modelName) {
  await fs.mkdir(RESULTS_ROOT, { recursive: true });
  const baseName = sanitizeModelName(modelName);

  let index = 1;
  while (index < 1000) {
    const suffix = String(index).padStart(3, '0');
    const runId = `${baseName}-${suffix}`;
    const runDir = path.join(RESULTS_ROOT, runId);

    try {
      await fs.mkdir(runDir);
      return { runDir, runId };
    } catch (error) {
      if (error.code === 'EEXIST') {
        index += 1;
        continue;
      }
      throw error;
    }
  }

  throw new Error('Unable to allocate a run directory.');
}

function sanitizeModelName(modelName) {
  const safe = (modelName || 'model')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return safe.length ? safe : 'model';
}

function computeSummary(responses, groups) {
  const total = responses.length;
  const summary = {
    total,
    group1: { count: 0, description: groups.group1 || '' },
    group2: { count: 0, description: groups.group2 || '' },
    undecided: { count: 0 }
  };

  responses.forEach(response => {
    if (response.group === '1') {
      summary.group1.count += 1;
    } else if (response.group === '2') {
      summary.group2.count += 1;
    } else {
      summary.undecided.count += 1;
    }
  });

  summary.group1.percentage = total ? (summary.group1.count / total) * 100 : 0;
  summary.group2.percentage = total ? (summary.group2.count / total) * 100 : 0;
  summary.undecided.percentage = total ? (summary.undecided.count / total) * 100 : 0;

  return summary;
}

function parseDecision(rawResponse) {
  if (typeof rawResponse !== 'string') {
    return null;
  }

  const match = rawResponse.match(/^\s*\{([12])\}\s*/);
  if (!match) {
    return null;
  }

  const group = match[1];
  const explanation = rawResponse.slice(match[0].length).trim();

  return {
    group,
    token: `{${group}}`,
    explanation
  };
}
