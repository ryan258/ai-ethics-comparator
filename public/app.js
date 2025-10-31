const MODEL_SUGGESTIONS = [
  'google/gemini-1.5-flash-latest',
  'anthropic/claude-3.5-sonnet',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'xai/grok-1.5-flash',
  'meta-llama/llama-3-70b-instruct',
  'mistralai/mistral-large-latest'
];

const modelInput = document.getElementById('model-input');
const modelSuggestions = document.getElementById('model-suggestions');
const paradoxSelect = document.getElementById('paradox-select');
const promptText = document.getElementById('prompt-text');
const responseText = document.getElementById('response-text');
const queryButton = document.getElementById('query-button');
const group1Input = document.getElementById('group1-input');
const group2Input = document.getElementById('group2-input');
const groupInputsSection = document.getElementById('group-inputs-section');
const iterationsInput = document.getElementById('iterations-input');
const systemPromptInput = document.getElementById('system-prompt-input');
const responseSummary = document.getElementById('response-summary');
const clearRunButton = document.getElementById('clear-run-button');
const rendererTarget = document.createElement('div');
const domParser = new DOMParser();

const queryTab = document.getElementById('query-tab');
const resultsTab = document.getElementById('results-tab');
const queryView = document.getElementById('query-view');
const resultsView = document.getElementById('results-view');
const resultsListLoading = document.getElementById('results-list-loading');
const resultsList = document.getElementById('results-list');
const resultsEmpty = document.getElementById('results-empty');
const resultsViewer = document.getElementById('results-viewer');
const resultsViewerSummary = document.getElementById('results-viewer-summary');
const resultsViewerDetails = document.getElementById('results-viewer-details');
const backToListButton = document.getElementById('back-to-list-button');
const exportCsvButton = document.getElementById('export-csv-button');
const resultsChartContainer = document.getElementById('results-chart-container');
const resultsChartCanvas = document.getElementById('results-chart');

let paradoxes = [];
let runs = [];
let currentViewedRun = null;
let currentChart = null;

function populateModelSuggestions() {
  modelSuggestions.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    modelSuggestions.appendChild(option);
  });
}

function populateParadoxes() {
  paradoxSelect.innerHTML = '';

  paradoxes.forEach(({ id, title }) => {
    const option = document.createElement('option');
    option.value = id;
    option.textContent = title;
    paradoxSelect.appendChild(option);
  });
}

function updatePromptDisplay() {
  const selectedParadox = getSelectedParadox();
  updateUIForParadoxType(selectedParadox);
  const prompt = buildPrompt(selectedParadox);

  if (prompt) {
    renderMarkdown(prompt, promptText, 'Select a paradox to view the full prompt.');
    promptText.classList.remove('placeholder');
    return prompt;
  }

  promptText.textContent = 'Select a paradox to view the full prompt.';
  promptText.classList.add('placeholder');
  return '';
}

function updateUIForParadoxType(paradox) {
  if (!paradox || !groupInputsSection) {
    return;
  }

  const paradoxType = paradox.type || 'trolley';

  if (paradoxType === 'trolley') {
    // Show group inputs for trolley-type paradoxes
    groupInputsSection.style.display = 'block';
  } else if (paradoxType === 'open_ended') {
    // Hide group inputs for open-ended paradoxes
    groupInputsSection.style.display = 'none';
  } else {
    // Default to showing group inputs
    groupInputsSection.style.display = 'block';
  }
}

async function loadParadoxes() {
  try {
    const response = await fetch('/api/paradoxes');
    if (!response.ok) {
      throw new Error('Failed to load paradoxes.');
    }

    paradoxes = await response.json();
    if (!Array.isArray(paradoxes) || paradoxes.length === 0) {
      throw new Error('No paradoxes available.');
    }

    populateParadoxes();
    const initialParadox = paradoxes[0];
    paradoxSelect.value = initialParadox.id;
    applyGroupDefaults(initialParadox);
    updatePromptDisplay();
  } catch (error) {
    console.error(error);
    promptText.textContent = error.message;
    queryButton.disabled = true;
  }
}

async function queryModel() {
  const modelName = modelInput.value.trim();
  const paradoxId = paradoxSelect.value;
  const selectedParadox = getSelectedParadox();
  const iterationCount = getIterationCount();
  if (iterationsInput) {
    iterationsInput.value = iterationCount;
  }

  if (!modelName || !paradoxId || !selectedParadox) {
    responseText.textContent = 'Select both a model and a paradox before querying.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  // Save model to localStorage
  try {
    localStorage.setItem('lastUsedModel', modelName);
  } catch (e) {
    console.warn('Failed to save model to localStorage:', e);
  }

  responseSummary.textContent = `Running ${iterationCount} iteration${iterationCount !== 1 ? 's' : ''}...`;
  responseSummary.classList.add('placeholder');
  responseText.classList.remove('error');
  responseText.classList.remove('placeholder');
  responseText.textContent = 'Contacting the model...';
  queryButton.disabled = true;
  queryButton.textContent = 'Working...';

  try {
    const systemPrompt = systemPromptInput ? systemPromptInput.value.trim() : '';

    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        modelName,
        paradoxId,
        iterations: iterationCount,
        groups: {
          group1: group1Input.value,
          group2: group2Input.value
        },
        systemPrompt: systemPrompt || undefined
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'The server returned an error.';
      throw new Error(errorMessage);
    }

    const runData = await response.json();
    updateDecisionViews(runData);

    if (runData.prompt) {
      renderMarkdown(runData.prompt, promptText, 'Select a paradox to view the full prompt.');
      promptText.classList.remove('placeholder');
    }
  } catch (error) {
    responseText.textContent = error.message;
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    resetDecisionSummary();
  } finally {
    queryButton.disabled = false;
    queryButton.textContent = 'Ask the Model';
  }
}

function renderMarkdown(markdownText, targetElement, fallbackText = '') {
  if (!markdownText) {
    targetElement.textContent = fallbackText;
    return;
  }

  const rawHtml = window.marked
    ? window.marked.parse(markdownText)
    : markdownText.replace(/\n/g, '<br />');

  rendererTarget.innerHTML = sanitizeHtml(rawHtml);

  targetElement.innerHTML = rendererTarget.innerHTML;
}

function sanitizeHtml(html) {
  const doc = domParser.parseFromString(html, 'text/html');
  doc.querySelectorAll('script, style, iframe, object, embed').forEach(el => el.remove());

  doc.body.querySelectorAll('*').forEach(el => {
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value;
      if (name.startsWith('on') || value.toLowerCase().includes('javascript:')) {
        el.removeAttribute(attr.name);
      }
    });
  });

  return doc.body.innerHTML;
}

function getSelectedParadox() {
  return paradoxes.find(p => p.id === paradoxSelect.value);
}

function applyGroupDefaults(paradox) {
  if (!paradox) {
    group1Input.value = '';
    group2Input.value = '';
    return;
  }

  group1Input.value = paradox.group1Default || '';
  group2Input.value = paradox.group2Default || '';
}

function buildPrompt(paradox) {
  if (!paradox || !paradox.promptTemplate) {
    return '';
  }

  const group1Text = normalizeGroupText(group1Input.value, paradox.group1Default);
  const group2Text = normalizeGroupText(group2Input.value, paradox.group2Default);

  const templateWithGroup1 = paradox.promptTemplate.replaceAll('{{GROUP1}}', group1Text);
  return templateWithGroup1.replaceAll('{{GROUP2}}', group2Text);
}

function normalizeGroupText(value, fallback) {
  const trimmed = (value || '').trim();
  return trimmed.length > 0 ? trimmed : fallback || '';
}

function resetDecisionSummary() {
  responseSummary.textContent = 'Run a query to see which group the model chooses to impact.';
  responseSummary.classList.add('placeholder');
}

function resetResponseText() {
  responseText.textContent = 'Choose a model and paradox, then ask the model to see its reasoning.';
  responseText.classList.add('placeholder');
  responseText.classList.remove('error');
}

function clearRun() {
  resetDecisionSummary();
  resetResponseText();
  if (clearRunButton) {
    clearRunButton.style.display = 'none';
  }
}

function getIterationCount() {
  const parsed = parseInt(iterationsInput?.value ?? '1', 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return 1;
  }
  return Math.min(parsed, 50);
}

function updateDecisionViews(runResult) {
  if (!runResult || !runResult.summary) {
    resetDecisionSummary();
    resetResponseText();
    return;
  }

  const summaryMarkdown = buildSummaryMarkdown(runResult);
  renderMarkdown(summaryMarkdown, responseSummary, 'Summary unavailable.');
  responseSummary.classList.remove('placeholder');

  const detailsMarkdown = buildDetailsMarkdown(runResult);
  renderMarkdown(detailsMarkdown, responseText, 'No iteration responses recorded.');
  responseText.classList.remove('error', 'placeholder');

  // Show clear button when there are results
  if (clearRunButton) {
    clearRunButton.style.display = 'inline-block';
  }
}

function buildSummaryMarkdown(runResult) {
  const lines = [];
  const summary = runResult.summary || {};
  const total = summary.total ?? runResult.iterationCount ?? runResult.responses?.length ?? 0;
  const paradoxType = runResult.paradoxType || 'trolley';

  lines.push(`**Run ID:** ${runResult.runId || 'unknown'}`);
  lines.push(`**Model:** ${runResult.modelName || 'n/a'}`);
  lines.push(`**Iterations:** ${total}`);
  lines.push('');

  if (paradoxType === 'open_ended') {
    // For open-ended paradoxes, show simple completion message
    lines.push(summary.message || `${total} iteration${total !== 1 ? 's' : ''} completed.`);
    lines.push('');
    lines.push('See iteration details below for the full responses.');
  } else {
    // For trolley-type paradoxes, show decision breakdown
    const group1 = summary.group1 || {};
    const group2 = summary.group2 || {};
    const undecided = summary.undecided || {};

    const group1Percent = formatPercentage(group1.percentage);
    const group2Percent = formatPercentage(group2.percentage);
    const undecidedPercent = formatPercentage(undecided.percentage);

    lines.push(
      `- \`{1}\` Group 1 — ${group1.description || 'No description'}: **${group1.count ?? 0}**${group1Percent ? ` (${group1Percent})` : ''}`
    );
    lines.push(
      `- \`{2}\` Group 2 — ${group2.description || 'No description'}: **${group2.count ?? 0}**${group2Percent ? ` (${group2Percent})` : ''}`
    );
    if ((undecided.count ?? 0) > 0) {
      lines.push(
        `- Undecided / invalid: **${undecided.count}**${undecidedPercent ? ` (${undecidedPercent})` : ''}`
      );
    }
  }

  lines.push('');
  lines.push(`Saved to \`results/${runResult.runId || 'run'}/run.json\``);

  return lines.join('\n');
}

function buildDetailsMarkdown(runResult) {
  const lines = [];
  lines.push('### Iteration Details');
  lines.push('');

  if (!Array.isArray(runResult.responses) || runResult.responses.length === 0) {
    lines.push('- No responses were recorded.');
    return lines.join('\n');
  }

  const paradoxType = runResult.paradoxType || 'trolley';

  if (paradoxType === 'open_ended') {
    // For open-ended paradoxes, show simple iteration responses
    runResult.responses.forEach(response => {
      const responseText = response.response || response.raw || '_No response recorded._';
      lines.push(`- **#${response.iteration}**`);
      const formattedResponse = responseText.trim().replace(/\n/g, '\n    ');
      lines.push(`  - ${formattedResponse}`);
    });
  } else {
    // For trolley-type paradoxes, show decision tokens and groups
    const group1Description = runResult.summary?.group1?.description || runResult.groups?.group1 || 'Group 1';
    const group2Description = runResult.summary?.group2?.description || runResult.groups?.group2 || 'Group 2';

    runResult.responses.forEach(response => {
      const token = response.decisionToken || '—';
      const isUndecided = !response.group || (response.group !== '1' && response.group !== '2');
      const groupLabel =
        response.group === '1'
          ? `Group 1 — ${group1Description}`
          : response.group === '2'
          ? `Group 2 — ${group2Description}`
          : 'Undecided / invalid';
      const explanation =
        response.explanation && response.explanation.trim().length > 0
          ? response.explanation.trim()
          : '_No explanation returned._';

      const warningFlag = isUndecided ? ' ⚠️ **UNDECIDED**' : '';
      lines.push(`- **#${response.iteration}** \`${token}\` • ${groupLabel}${warningFlag}`);
      const formattedExplanation = explanation.replace(/\n/g, '\n    ');
      lines.push(`  - ${formattedExplanation}`);
    });
  }

  return lines.join('\n');
}

function formatPercentage(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '';
  }
  const clean = Number(value.toFixed(1));
  if (Number.isNaN(clean)) {
    return '';
  }
  return `${clean % 1 === 0 ? clean.toFixed(0) : clean}%`;
}

modelInput.addEventListener('input', () => {
  resetResponseText();
  resetDecisionSummary();
});

paradoxSelect.addEventListener('change', () => {
  const selectedParadox = getSelectedParadox();
  applyGroupDefaults(selectedParadox);
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

group1Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

group2Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
});

if (iterationsInput) {
  iterationsInput.addEventListener('input', () => {
    resetDecisionSummary();
    resetResponseText();
  });

  iterationsInput.addEventListener('change', () => {
    iterationsInput.value = getIterationCount();
  });
}

queryButton.addEventListener('click', queryModel);

if (clearRunButton) {
  clearRunButton.addEventListener('click', clearRun);
}

// Tab switching
function switchToQueryView() {
  queryView.style.display = 'block';
  resultsView.style.display = 'none';
  queryTab.classList.add('active');
  resultsTab.classList.remove('active');
}

function switchToResultsView() {
  queryView.style.display = 'none';
  resultsView.style.display = 'block';
  queryTab.classList.remove('active');
  resultsTab.classList.add('active');
  loadRuns();
}

if (queryTab) {
  queryTab.addEventListener('click', switchToQueryView);
}

if (resultsTab) {
  resultsTab.addEventListener('click', switchToResultsView);
}

// Results management
async function loadRuns() {
  resultsListLoading.style.display = 'block';
  resultsList.style.display = 'none';
  resultsEmpty.style.display = 'none';
  resultsViewer.style.display = 'none';

  try {
    const response = await fetch('/api/runs');
    if (!response.ok) {
      throw new Error('Failed to load runs');
    }

    runs = await response.json();

    if (runs.length === 0) {
      resultsListLoading.style.display = 'none';
      resultsEmpty.style.display = 'block';
      return;
    }

    displayRunsList();
  } catch (error) {
    console.error('Error loading runs:', error);
    resultsListLoading.textContent = 'Error loading runs. Please try again.';
  }
}

function displayRunsList() {
  resultsListLoading.style.display = 'none';
  resultsList.style.display = 'block';
  resultsList.innerHTML = '';

  runs.forEach(run => {
    const runItem = document.createElement('div');
    runItem.className = 'run-item';
    runItem.style.cursor = 'pointer';
    runItem.style.padding = '10px';
    runItem.style.marginBottom = '10px';
    runItem.style.border = '1px solid #ccc';
    runItem.style.borderRadius = '4px';

    const timestamp = new Date(run.timestamp).toLocaleString();
    runItem.innerHTML = `
      <strong>${run.runId}</strong><br/>
      Model: ${run.modelName}<br/>
      Paradox: ${run.paradoxId}<br/>
      Iterations: ${run.iterationCount}<br/>
      Date: ${timestamp}
    `;

    runItem.addEventListener('click', () => viewRun(run.runId));
    resultsList.appendChild(runItem);
  });
}

async function viewRun(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    if (!response.ok) {
      throw new Error('Failed to load run details');
    }

    const runData = await response.json();
    currentViewedRun = runData;

    // Hide list, show viewer
    resultsList.parentElement.style.display = 'none';
    resultsViewer.style.display = 'block';

    // Use existing functions to render the run data
    const summaryMarkdown = buildSummaryMarkdown(runData);
    renderMarkdown(summaryMarkdown, resultsViewerSummary, 'Summary unavailable.');

    const detailsMarkdown = buildDetailsMarkdown(runData);
    renderMarkdown(detailsMarkdown, resultsViewerDetails, 'No iteration responses recorded.');

    // Render chart for trolley-type paradoxes
    renderResultsChart(runData);
  } catch (error) {
    console.error('Error loading run:', error);
    alert('Failed to load run details. Please try again.');
  }
}

function renderResultsChart(runData) {
  // Destroy existing chart if any
  if (currentChart) {
    currentChart.destroy();
    currentChart = null;
  }

  const paradoxType = runData.paradoxType || 'trolley';

  // Only show chart for trolley-type paradoxes
  if (paradoxType !== 'trolley' || !runData.summary) {
    resultsChartContainer.style.display = 'none';
    return;
  }

  resultsChartContainer.style.display = 'block';

  const summary = runData.summary;
  const labels = [];
  const data = [];
  const colors = [];

  if (summary.group1) {
    labels.push('Group 1');
    data.push(summary.group1.count || 0);
    colors.push('rgba(54, 162, 235, 0.8)');
  }

  if (summary.group2) {
    labels.push('Group 2');
    data.push(summary.group2.count || 0);
    colors.push('rgba(255, 99, 132, 0.8)');
  }

  if (summary.undecided && summary.undecided.count > 0) {
    labels.push('Undecided');
    data.push(summary.undecided.count);
    colors.push('rgba(201, 203, 207, 0.8)');
  }

  if (!window.Chart) {
    console.warn('Chart.js not loaded');
    resultsChartContainer.style.display = 'none';
    return;
  }

  currentChart = new Chart(resultsChartCanvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Decision Count',
        data: data,
        backgroundColor: colors,
        borderColor: colors.map(c => c.replace('0.8', '1')),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: false
        },
        title: {
          display: true,
          text: 'Decision Distribution'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            stepSize: 1
          }
        }
      }
    }
  });
}

function exportToCSV(runData) {
  if (!runData || !runData.responses || runData.responses.length === 0) {
    alert('No data to export');
    return;
  }

  const paradoxType = runData.paradoxType || 'trolley';
  const rows = [];

  // Header row
  if (paradoxType === 'trolley') {
    rows.push(['Iteration', 'Decision Token', 'Group', 'Explanation', 'Timestamp']);
  } else {
    rows.push(['Iteration', 'Response', 'Timestamp']);
  }

  // Data rows
  runData.responses.forEach(response => {
    if (paradoxType === 'trolley') {
      rows.push([
        response.iteration || '',
        response.decisionToken || '',
        response.group || '',
        (response.explanation || '').replace(/"/g, '""'),
        response.timestamp || ''
      ]);
    } else {
      rows.push([
        response.iteration || '',
        (response.response || response.raw || '').replace(/"/g, '""'),
        response.timestamp || ''
      ]);
    }
  });

  // Convert to CSV string
  const csvContent = rows.map(row =>
    row.map(cell => `"${cell}"`).join(',')
  ).join('\n');

  // Download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `${runData.runId || 'run'}.csv`);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

if (backToListButton) {
  backToListButton.addEventListener('click', () => {
    resultsViewer.style.display = 'none';
    resultsList.parentElement.style.display = 'block';
  });
}

if (exportCsvButton) {
  exportCsvButton.addEventListener('click', () => {
    if (currentViewedRun) {
      exportToCSV(currentViewedRun);
    } else {
      alert('No run data available to export');
    }
  });
}

populateModelSuggestions();
loadParadoxes();

// Load last-used model from localStorage
try {
  const lastUsedModel = localStorage.getItem('lastUsedModel');
  if (lastUsedModel && modelInput) {
    modelInput.value = lastUsedModel;
  }
} catch (e) {
  console.warn('Failed to load model from localStorage:', e);
}
