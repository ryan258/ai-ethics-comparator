const MODEL_SUGGESTIONS = [
  'openrouter/polaris-alpha',
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

// Generation parameters
const temperatureInput = document.getElementById('temperature-input');
const topPInput = document.getElementById('top-p-input');
const maxTokensInput = document.getElementById('max-tokens-input');
const seedInput = document.getElementById('seed-input');
const frequencyPenaltyInput = document.getElementById('frequency-penalty-input');
const presencePenaltyInput = document.getElementById('presence-penalty-input');
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
const exportJsonButton = document.getElementById('export-json-button');
const batchExportButton = document.getElementById('batch-export-button');
const resultsChartContainer = document.getElementById('results-chart-container');
const resultsChartCanvas = document.getElementById('results-chart');
const generateInsightButton = document.getElementById('generate-insight-button');
const analystModelInput = document.getElementById('analyst-model-input');
const insightLoading = document.getElementById('insight-loading');
const insightResult = document.getElementById('insight-result');
const batchModeToggle = document.getElementById('batch-mode-toggle');
const batchModelSelection = document.getElementById('batch-model-selection');
const batchModelCheckboxes = document.getElementById('batch-model-checkboxes');
const batchProgress = document.getElementById('batch-progress');
const batchProgressFill = document.getElementById('batch-progress-fill');
const batchProgressText = document.getElementById('batch-progress-text');
const compareModeToggle = document.getElementById('compare-mode-toggle');
const startComparisonButton = document.getElementById('start-comparison-button');
const comparisonInstructions = document.getElementById('comparison-instructions');
const comparisonViewer = document.getElementById('comparison-viewer');
const comparisonStats = document.getElementById('comparison-stats');
const comparisonContent = document.getElementById('comparison-content');
const backToListFromComparisonButton = document.getElementById('back-to-list-from-comparison-button');
const queryInsightPanel = document.getElementById('query-insight-panel');
const queryAnalystModelInput = document.getElementById('query-analyst-model-input');
const queryGenerateInsightButton = document.getElementById('query-generate-insight-button');
const queryInsightLoading = document.getElementById('query-insight-loading');
const queryInsightResult = document.getElementById('query-insight-result');

let paradoxes = [];
let runs = [];
let currentViewedRun = null;
let currentQueryRun = null; // Track the current run data in query view
let currentChart = null;
let isBatchMode = false;
let isCompareMode = false;
let selectedRunsForComparison = [];
let isViewingRun = false; // Track if user is viewing a specific run

function gatherGenerationParams() {
  const params = {
    temperature: parseFloat(temperatureInput.value) || 1.0,
    top_p: parseFloat(topPInput.value) || 1.0,
    max_tokens: parseInt(maxTokensInput.value) || 1000,
    frequency_penalty: parseFloat(frequencyPenaltyInput.value) || 0,
    presence_penalty: parseFloat(presencePenaltyInput.value) || 0
  };

  // Only include seed if it's set
  const seedValue = parseInt(seedInput.value);
  if (!isNaN(seedValue) && seedValue >= 0) {
    params.seed = seedValue;
  }

  return params;
}

function populateModelSuggestions() {
  modelSuggestions.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    modelSuggestions.appendChild(option);
  });
}

function populateBatchModelCheckboxes() {
  batchModelCheckboxes.innerHTML = '';
  MODEL_SUGGESTIONS.forEach(modelName => {
    const label = document.createElement('label');
    label.className = 'batch-model-label';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = modelName;
    checkbox.className = 'batch-model-checkbox';

    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(modelName));
    batchModelCheckboxes.appendChild(label);
  });
}

function toggleBatchMode() {
  isBatchMode = batchModeToggle.checked;

  if (isBatchMode) {
    modelInput.classList.add('hidden');
    batchModelSelection.classList.remove('hidden');
    populateBatchModelCheckboxes();
  } else {
    modelInput.classList.remove('hidden');
    batchModelSelection.classList.add('hidden');
  }
}

function getSelectedBatchModels() {
  const checkboxes = document.querySelectorAll('.batch-model-checkbox:checked');
  return Array.from(checkboxes).map(cb => cb.value);
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
    groupInputsSection.classList.remove('hidden');
  } else if (paradoxType === 'open_ended') {
    // Hide group inputs for open-ended paradoxes
    groupInputsSection.classList.add('hidden');
  } else {
    // Default to showing group inputs
    groupInputsSection.classList.remove('hidden');
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
  const paradoxId = paradoxSelect.value;
  const selectedParadox = getSelectedParadox();
  const iterationCount = getIterationCount();
  if (iterationsInput) {
    iterationsInput.value = iterationCount;
  }

  // Check if batch mode is enabled
  if (isBatchMode) {
    await runBatchQuery();
    return;
  }

  // Single model mode
  const modelName = modelInput.value.trim();

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
    const genParams = gatherGenerationParams();

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
        systemPrompt: systemPrompt || undefined,
        params: genParams
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'The server returned an error.';
      throw new Error(errorMessage);
    }

    const runData = await response.json();
    currentQueryRun = runData; // Store run data for insight generation
    updateDecisionViews(runData);

    if (runData.prompt) {
      renderMarkdown(runData.prompt, promptText, 'Select a paradox to view the full prompt.');
      promptText.classList.remove('placeholder');
    }

    // Show insight panel after successful run
    if (queryInsightPanel) {
      queryInsightPanel.classList.remove('hidden');
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

async function runBatchQuery() {
  const selectedModels = getSelectedBatchModels();
  const paradoxId = paradoxSelect.value;
  const iterationCount = getIterationCount();

  if (selectedModels.length === 0) {
    responseText.textContent = 'Please select at least one model for batch run.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  if (!paradoxId) {
    responseText.textContent = 'Please select a paradox.';
    responseText.classList.add('error');
    responseText.classList.remove('placeholder');
    return;
  }

  // Show progress bar
  batchProgress.classList.remove('hidden');
  batchProgressFill.style.width = '0%';
  batchProgressText.textContent = 'Starting batch run...';

  // Reset results display
  responseText.innerHTML = '<div class="batch-results-header">Batch Run Results</div>';
  queryButton.disabled = true;
  queryButton.textContent = 'Running Batch...';
  responseText.classList.remove('error', 'placeholder');

  const results = [];
  const errors = [];

  for (let i = 0; i < selectedModels.length; i++) {
    const modelName = selectedModels[i];
    const progress = ((i / selectedModels.length) * 100).toFixed(0);
    batchProgressFill.style.width = `${progress}%`;
    batchProgressText.textContent = `Processing ${i + 1}/${selectedModels.length}: ${modelName}`;

    try {
      const systemPrompt = systemPromptInput ? systemPromptInput.value.trim() : '';
      const genParams = gatherGenerationParams();

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
          systemPrompt: systemPrompt || undefined,
          params: genParams
        })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        const errorMessage = errorBody.error || 'The server returned an error.';
        throw new Error(errorMessage);
      }

      const runData = await response.json();
      results.push({ modelName, runData, success: true });
    } catch (error) {
      errors.push({ modelName, error: error.message });
      results.push({ modelName, error: error.message, success: false });
    }
  }

  // Complete progress
  batchProgressFill.style.width = '100%';
  batchProgressText.textContent = `Batch run complete! Processed ${selectedModels.length} model${selectedModels.length !== 1 ? 's' : ''}.`;

  // Display results summary
  displayBatchResults(results);

  queryButton.disabled = false;
  queryButton.textContent = 'Ask the Model';

  // Show clear button
  if (clearRunButton) {
    clearRunButton.classList.remove('hidden');
  }
}

function displayBatchResults(results) {
  const successCount = results.filter(r => r.success).length;
  const errorCount = results.filter(r => !r.success).length;

  let html = `<div class="batch-summary">Batch Run Complete</div>`;
  html += `<div class="batch-result-card">`;
  html += `<strong>Summary:</strong> ${successCount} succeeded, ${errorCount} failed<br/>`;
  html += `</div>`;

  results.forEach(result => {
    if (result.success) {
      const runData = result.runData;
      const summary = runData.summary || {};
      const paradoxType = runData.paradoxType || 'trolley';

      html += `<div class="batch-success-card">`;
      html += `<div class="batch-card-header success">✓ ${result.modelName}</div>`;
      html += `<div class="batch-card-details">`;
      if (paradoxType === 'trolley') {
        const g1 = summary.group1 || {};
        const g2 = summary.group2 || {};
        html += `Group 1: ${g1.count || 0} (${formatPercentage(g1.percentage)}), `;
        html += `Group 2: ${g2.count || 0} (${formatPercentage(g2.percentage)})`;
      } else {
        html += `${runData.iterationCount} iterations completed`;
      }

      html += `</div></div>`;
    } else {
      html += `<div class="batch-error-card">`;
      html += `<div class="batch-card-header error">✗ ${result.modelName}</div>`;
      html += `<div class="batch-card-details">Error: ${result.error}</div>`;
      html += `</div>`;
    }
  });

  html += `<div class="batch-info-box">`;
  html += `All results have been saved to the <strong>Results</strong> tab. Click on the Results tab to view detailed information for each run.`;
  html += `</div>`;

  responseText.innerHTML = html;
  responseSummary.textContent = `Batch run completed: ${successCount}/${results.length} models successful`;
  responseSummary.classList.remove('placeholder');
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

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function sanitizeHtml(html) {
  // Use DOMPurify for robust XSS protection
  if (typeof DOMPurify !== 'undefined') {
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'code', 'pre', 'blockquote', 'div', 'span'],
      ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'style'],
      ALLOW_DATA_ATTR: false
    });
  }

  // Fallback if DOMPurify is not available
  const doc = domParser.parseFromString(html, 'text/html');
  doc.querySelectorAll('script, style, iframe, object, embed, form, input, textarea, button').forEach(el => el.remove());

  doc.body.querySelectorAll('*').forEach(el => {
    [...el.attributes].forEach(attr => {
      const name = attr.name.toLowerCase();
      const value = attr.value;
      if (name.startsWith('on') || name.startsWith('data-') || value.toLowerCase().includes('javascript:')) {
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
  currentQueryRun = null; // Clear query run data
  if (clearRunButton) {
    clearRunButton.classList.add('hidden');
  }
  if (batchProgress) {
    batchProgress.classList.add('hidden');
  }
  if (queryInsightPanel) {
    queryInsightPanel.classList.add('hidden');
  }
  if (queryInsightResult) {
    queryInsightResult.classList.add('hidden');
    queryInsightResult.innerHTML = '';
  }
  if (queryInsightLoading) {
    queryInsightLoading.classList.add('hidden');
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
    clearRunButton.classList.remove('hidden');
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

function hideQueryInsightPanel() {
  if (queryInsightPanel) {
    queryInsightPanel.classList.add('hidden');
  }
  if (queryInsightResult) {
    queryInsightResult.classList.add('hidden');
  }
  currentQueryRun = null;
}

modelInput.addEventListener('input', () => {
  resetResponseText();
  resetDecisionSummary();
  hideQueryInsightPanel();
});

paradoxSelect.addEventListener('change', () => {
  const selectedParadox = getSelectedParadox();
  applyGroupDefaults(selectedParadox);
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
  hideQueryInsightPanel();
});

group1Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
  hideQueryInsightPanel();
});

group2Input.addEventListener('input', () => {
  updatePromptDisplay();
  resetResponseText();
  resetDecisionSummary();
  hideQueryInsightPanel();
});

if (iterationsInput) {
  iterationsInput.addEventListener('input', () => {
    resetDecisionSummary();
    resetResponseText();
    hideQueryInsightPanel();
  });

  iterationsInput.addEventListener('change', () => {
    iterationsInput.value = getIterationCount();
  });
}

queryButton.addEventListener('click', queryModel);

if (clearRunButton) {
  clearRunButton.addEventListener('click', clearRun);
}

if (batchModeToggle) {
  batchModeToggle.addEventListener('change', toggleBatchMode);
}

// Tab switching
function switchToQueryView() {
  queryView.classList.add('block');
  queryView.classList.remove('hidden');
  resultsView.classList.add('hidden');
  resultsView.classList.remove('block');
  queryTab.classList.add('active');
  resultsTab.classList.remove('active');
}

function switchToResultsView() {
  queryView.classList.add('hidden');
  queryView.classList.remove('block');
  resultsView.classList.add('block');
  resultsView.classList.remove('hidden');
  resultsTab.classList.add('active');
  queryTab.classList.remove('active');

  // Only reload runs list if not currently viewing a specific run
  if (!isViewingRun) {
    loadRuns();
  }
}

if (queryTab) {
  queryTab.addEventListener('click', switchToQueryView);
}

if (resultsTab) {
  resultsTab.addEventListener('click', switchToResultsView);
}

// Results management
async function loadRuns() {
  resultsListLoading.classList.remove('hidden');
  resultsList.classList.add('hidden');
  resultsEmpty.classList.add('hidden');
  resultsViewer.classList.add('hidden');
  isViewingRun = false; // Reset to list view state

  try {
    const response = await fetch('/api/runs');
    if (!response.ok) {
      throw new Error('Failed to load runs');
    }

    runs = await response.json();

    if (runs.length === 0) {
      resultsListLoading.classList.add('hidden');
      resultsEmpty.classList.remove('hidden');
      return;
    }

    displayRunsList();
  } catch (error) {
    console.error('Error loading runs:', error);
    resultsListLoading.textContent = 'Error loading runs. Please try again.';
  }
}

function displayRunsList() {
  resultsListLoading.classList.add('hidden');
  resultsList.classList.remove('hidden');
  resultsList.innerHTML = '';

  runs.forEach(run => {
    const runItem = document.createElement('div');
    runItem.className = 'run-card';


    const timestamp = new Date(run.timestamp).toLocaleString();

    if (isCompareMode) {
      // Add checkbox for comparison mode
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = run.runId;
      checkbox.checked = selectedRunsForComparison.includes(run.runId);
      checkbox.className = 'compare-checkbox';
      checkbox.addEventListener('change', (e) => {
        e.stopPropagation();
        toggleRunSelection(run.runId);
      });
      runItem.appendChild(checkbox);

      const contentDiv = document.createElement('div');
      contentDiv.className = 'run-content';
      contentDiv.innerHTML = `
        <strong>${escapeHtml(run.runId)}</strong><br/>
        Model: ${escapeHtml(run.modelName)}<br/>
        Paradox: ${escapeHtml(run.paradoxId)}<br/>
        Iterations: ${run.iterationCount}<br/>
        Date: ${escapeHtml(timestamp)}
      `;
      runItem.appendChild(contentDiv);
    } else {
      // Normal mode - clickable to view
      runItem.innerHTML = `
        <strong>${escapeHtml(run.runId)}</strong><br/>
        Model: ${escapeHtml(run.modelName)}<br/>
        Paradox: ${escapeHtml(run.paradoxId)}<br/>
        Iterations: ${run.iterationCount}<br/>
        Date: ${escapeHtml(timestamp)}
      `;
      runItem.addEventListener('click', () => viewRun(run.runId));
    }

    resultsList.appendChild(runItem);
  });
}

function toggleCompareMode() {
  isCompareMode = !isCompareMode;
  selectedRunsForComparison = [];

  if (isCompareMode) {
    comparisonInstructions.classList.remove('hidden');
    startComparisonButton.classList.remove('hidden');
    compareModeToggle.textContent = 'Cancel Comparison';
  } else {
    comparisonInstructions.classList.add('hidden');
    startComparisonButton.classList.add('hidden');
    compareModeToggle.textContent = 'Compare Runs';
    selectedRunsForComparison = [];
  }

  displayRunsList();
}

function toggleRunSelection(runId) {
  const index = selectedRunsForComparison.indexOf(runId);
  if (index > -1) {
    selectedRunsForComparison.splice(index, 1);
  } else {
    if (selectedRunsForComparison.length >= 3) {
      alert('You can only compare up to 3 runs at a time. Deselect one to continue.');
      return;
    }
    selectedRunsForComparison.push(runId);
  }

  // Update button text
  if (selectedRunsForComparison.length >= 2) {
    startComparisonButton.textContent = `Compare ${selectedRunsForComparison.length} Runs`;
    startComparisonButton.disabled = false;
  } else {
    startComparisonButton.textContent = 'Compare Selected';
    startComparisonButton.disabled = true;
  }
}

async function viewRun(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    if (!response.ok) {
      throw new Error('Failed to load run details');
    }

    const runData = await response.json();
    currentViewedRun = runData;
    isViewingRun = true; // Mark that we're viewing a specific run

    // Hide list, show viewer
    resultsList.parentElement.classList.add('hidden');
    resultsViewer.classList.remove('hidden');

    // Use existing functions to render the run data
    const summaryMarkdown = buildSummaryMarkdown(runData);
    renderMarkdown(summaryMarkdown, resultsViewerSummary, 'Summary unavailable.');

    const detailsMarkdown = buildDetailsMarkdown(runData);
    renderMarkdown(detailsMarkdown, resultsViewerDetails, 'No iteration responses recorded.');

    // Render chart for trolley-type paradoxes
    renderResultsChart(runData);

    // Display saved insights if they exist
    if (runData.insights && runData.insights.length > 0) {
      displaySavedInsights(runData.insights);
    } else {
      // Clear insight panel if no saved insights
      if (insightResult) {
        insightResult.classList.add('hidden');
        insightResult.innerHTML = '';
      }
      if (insightLoading) {
        insightLoading.classList.add('hidden');
      }
    }
  } catch (error) {
    console.error('Error loading run:', error);
    alert('Failed to load run details. Please try again.');
  }
}

function displaySavedInsights(insights) {
  if (!insightResult) return;

  insightLoading.classList.add('hidden');
  insightResult.classList.remove('hidden');

  let html = '<div class="insight-header">';
  html += '<strong>📊 Saved Insights</strong> ';
  html += `<span style="font-size: 0.9em; opacity: 0.8;">(${insights.length} analysis${insights.length !== 1 ? 'es' : ''})</span>`;
  html += '</div>';

  insights.forEach((insight, index) => {
    const date = new Date(insight.timestamp).toLocaleString();

    html += '<div style="margin-bottom: 20px; padding: 15px; background: #f5f5f5; border-radius: 4px; color: darkslategray;">';
    html += `<div style="font-size: 0.85em; color: #666; margin-bottom: 10px;">`;
    html += `<strong>Analysis ${index + 1}</strong> | `;
    html += `${date} | `;
    html += `Model: ${escapeHtml(insight.analystModel)}`;
    html += '</div>';

    // Parse markdown and render the insight content
    html += '<div class="insight-card">';
    if (window.marked) {
      html += window.marked.parse(insight.content);
    } else {
      // Fallback if marked is not available
      const sanitized = sanitizeHtml(insight.content.replace(/\n/g, '<br />'));
      html += sanitized;
    }
    html += '</div>';
    html += '</div>';
  });

  insightResult.innerHTML = html;

  // Update button text to indicate insights exist
  if (generateInsightButton) {
    generateInsightButton.textContent = 'Generate New Insight';
  }
}

async function startComparison() {
  if (selectedRunsForComparison.length < 2) {
    alert('Please select at least 2 runs to compare.');
    return;
  }

  try {
    // Fetch all selected runs
    const runDataPromises = selectedRunsForComparison.map(runId =>
      fetch(`/api/runs/${runId}`).then(r => r.json())
    );
    const runDataList = await Promise.all(runDataPromises);

    // Hide list, show comparison viewer
    resultsList.parentElement.classList.add('hidden');
    comparisonViewer.classList.remove('hidden');
    isViewingRun = true; // Mark that we're viewing comparison (not the list)

    displayComparison(runDataList);
  } catch (error) {
    console.error('Error loading runs for comparison:', error);
    alert('Failed to load run data for comparison. Please try again.');
  }
}

function calculateChiSquare(run1, run2) {
  // Only calculate for trolley-type paradoxes
  if (!run1.summary || !run2.summary || (run1.paradoxType !== 'trolley') || (run2.paradoxType !== 'trolley')) {
    return null;
  }

  const observed1 = [
    run1.summary.group1?.count || 0,
    run1.summary.group2?.count || 0
  ];
  const observed2 = [
    run2.summary.group1?.count || 0,
    run2.summary.group2?.count || 0
  ];

  const n1 = observed1[0] + observed1[1];
  const n2 = observed2[0] + observed2[1];

  if (n1 === 0 || n2 === 0) {
    return null;
  }

  // Calculate expected frequencies
  const total1 = observed1[0] + observed2[0];
  const total2 = observed1[1] + observed2[1];
  const grandTotal = n1 + n2;

  const expected1 = [
    (n1 * total1) / grandTotal,
    (n1 * total2) / grandTotal
  ];
  const expected2 = [
    (n2 * total1) / grandTotal,
    (n2 * total2) / grandTotal
  ];

  // Calculate chi-square statistic
  let chiSquare = 0;
  for (let i = 0; i < 2; i++) {
    if (expected1[i] > 0) {
      chiSquare += Math.pow(observed1[i] - expected1[i], 2) / expected1[i];
    }
    if (expected2[i] > 0) {
      chiSquare += Math.pow(observed2[i] - expected2[i], 2) / expected2[i];
    }
  }

  // Calculate p-value (df = 1 for 2x2 contingency table)
  const pValue = chiSquarePValue(chiSquare, 1);

  return {
    chiSquare: chiSquare.toFixed(4),
    pValue: pValue.toFixed(4),
    degreesOfFreedom: 1,
    significant: pValue < 0.05
  };
}

function chiSquarePValue(chiSquare, df) {
  // Simplified chi-square p-value approximation for df=1
  // Using the complementary error function approximation
  if (df !== 1) return 0;

  const z = Math.sqrt(chiSquare);
  // Approximation of the complementary error function
  const t = 1 / (1 + 0.5 * z);
  const erfcZ = t * Math.exp(-z * z - 1.26551223 +
    t * (1.00002368 +
      t * (0.37409196 +
        t * (0.09678418 +
          t * (-0.18628806 +
            t * (0.27886807 +
              t * (-1.13520398 +
                t * (1.48851587 +
                  t * (-0.82215223 +
                    t * 0.17087277)))))))));

  return erfcZ;
}

function displayComparison(runDataList) {
  comparisonContent.innerHTML = '';
  comparisonStats.innerHTML = '';

  // Display statistical comparison for trolley-type runs
  if (runDataList.length === 2 && runDataList[0].paradoxType === 'trolley' && runDataList[1].paradoxType === 'trolley') {
    const stats = calculateChiSquare(runDataList[0], runDataList[1]);
    if (stats) {
      const significanceText = stats.significant
        ? '<strong class="text-success">statistically significant</strong>'
        : '<strong class="text-muted">not statistically significant</strong>';

      comparisonStats.innerHTML = `
        <div class="stats-analysis-box">
          <h3 class="stats-header">Statistical Analysis</h3>
          <p class="stats-note">Chi-square test results for decision distribution:</p>
          <ul class="stats-list">
            <li><strong>χ² statistic:</strong> ${stats.chiSquare}</li>
            <li><strong>Degrees of freedom:</strong> ${stats.degreesOfFreedom}</li>
            <li><strong>p-value:</strong> ${stats.pValue}</li>
            <li><strong>Result:</strong> The difference in decision distributions is ${significanceText} (α = 0.05)</li>
          </ul>
          <p class="stats-note">
            ${stats.significant
          ? 'The p-value is less than 0.05, indicating the two runs have significantly different decision distributions.'
          : 'The p-value is greater than 0.05, indicating the two runs do not have significantly different decision distributions.'}
          </p>
        </div>
      `;
    }
  }

  // Set grid columns based on number of runs
  if (runDataList.length === 2) {
    comparisonContent.className = 'comparison-grid-2';
  } else {
    comparisonContent.className = 'comparison-grid-3';
  }

  runDataList.forEach(runData => {
    const runCard = document.createElement('div');
    runCard.className = 'comparison-card';

    const summaryDiv = document.createElement('div');
    const summaryMarkdown = buildSummaryMarkdown(runData);
    renderMarkdown(summaryMarkdown, summaryDiv, 'Summary unavailable.');

    if (runData.paradoxType === 'trolley' && runData.summary) {
      const chartDiv = document.createElement('div');
      chartDiv.className = 'chart-container';
      chartDiv.innerHTML = '<canvas></canvas>';
      runCard.appendChild(summaryDiv);
      runCard.appendChild(chartDiv);

      // Render mini chart
      const canvas = chartDiv.querySelector('canvas');
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

      new Chart(canvas, {
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
            legend: { display: false },
            title: { display: false }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1 }
            }
          }
        }
      });
    } else {
      runCard.appendChild(summaryDiv);
    }

    comparisonContent.appendChild(runCard);
  });
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
    resultsChartContainer.classList.add('hidden');
    return;
  }

  resultsChartContainer.classList.remove('hidden');

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
    resultsChartContainer.classList.add('hidden');
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
  link.classList.add('invisible');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function exportToJSON(runData) {
  if (!runData) {
    alert('No data to export');
    return;
  }

  const jsonContent = JSON.stringify(runData, null, 2);
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', `${runData.runId || 'run'}.json`);
  link.classList.add('invisible');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function batchExportAllRuns() {
  if (!runs || runs.length === 0) {
    alert('No runs available to export');
    return;
  }

  const confirmExport = confirm(`This will export all ${runs.length} run(s) as a single JSON file. Continue?`);
  if (!confirmExport) {
    return;
  }

  try {
    // Fetch all run data
    batchExportButton.disabled = true;
    batchExportButton.textContent = 'Exporting...';

    const runDataPromises = runs.map(run =>
      fetch(`/api/runs/${run.runId}`).then(r => r.json())
    );
    const allRunData = await Promise.all(runDataPromises);

    // Create a combined export
    const exportData = {
      exportDate: new Date().toISOString(),
      totalRuns: allRunData.length,
      runs: allRunData
    };

    const jsonContent = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
    link.setAttribute('href', url);
    link.setAttribute('download', `ai-ethics-comparator-export-${timestamp}.json`);
    link.classList.add('invisible');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    batchExportButton.textContent = 'Export All (ZIP)';
    batchExportButton.disabled = false;
  } catch (error) {
    console.error('Error during batch export:', error);
    alert('Failed to export runs. Please try again.');
    batchExportButton.textContent = 'Export All (ZIP)';
    batchExportButton.disabled = false;
  }
}

async function generateInsight() {
  if (!currentViewedRun) {
    alert('No run data available to analyze');
    return;
  }

  try {
    // Get analyst model from input, or use default
    const analystModel = analystModelInput?.value?.trim() || 'x-ai/grok-4.1-fast:free';

    // Show loading state
    generateInsightButton.disabled = true;
    generateInsightButton.textContent = 'Generating...';
    insightLoading.classList.remove('hidden');
    insightResult.classList.add('hidden');

    const response = await fetch('/api/insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        runData: currentViewedRun,
        analystModel: analystModel
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'Failed to generate insight.';
      throw new Error(errorMessage);
    }

    const result = await response.json();

    // Reload the run data to show the saved insight
    if (currentViewedRun && currentViewedRun.runId) {
      try {
        const reloadResponse = await fetch(`/api/runs/${currentViewedRun.runId}`);
        if (reloadResponse.ok) {
          const updatedRunData = await reloadResponse.json();
          currentViewedRun = updatedRunData;

          // Display all saved insights (including the new one)
          if (updatedRunData.insights && updatedRunData.insights.length > 0) {
            displaySavedInsights(updatedRunData.insights);
          }
        }
      } catch (reloadError) {
        console.error('Error reloading run data:', reloadError);
        // Don't fail - still show the generated insight
      }
    }

    // If reload failed or no runId, show the newly generated insight
    if (!insightResult.innerHTML || insightResult.innerHTML.indexOf('Saved Insights') === -1) {
      insightLoading.classList.add('hidden');
      insightResult.classList.remove('hidden');

      let insightHtml = '<div class="insight-header-card">';
      insightHtml += `<strong>✨ New Insight Generated</strong><br>`;
      insightHtml += `<span class="insight-model-info">Analyst Model: ${escapeHtml(result.model)}</span>`;
      insightHtml += '</div>';
      insightHtml += '<div class="insight-content">';
      const insightContent = result.insight; // Assuming result.insight holds the content
      if (window.marked) {
        insightHtml += window.marked.parse(insightContent);
      } else {
        insightHtml += sanitizeHtml(insightContent.replace(/\n/g, '<br />'));
      }

      insightHtml += '</div>';
      insightResult.innerHTML = insightHtml;
    }

    generateInsightButton.disabled = false;
    generateInsightButton.textContent = 'Generate Another Insight';
  } catch (error) {
    console.error('Error generating insight:', error);
    insightLoading.classList.add('hidden');
    insightResult.classList.remove('hidden');
    insightResult.innerHTML = `<div class="error-message"><strong>Error:</strong> ${error.message}</div>`;
    generateInsightButton.disabled = false;
    generateInsightButton.textContent = 'Generate AI Insight Summary';
  }
}

if (backToListButton) {
  backToListButton.addEventListener('click', () => {
    resultsViewer.classList.add('hidden');
    resultsList.parentElement.classList.remove('hidden');
    isViewingRun = false; // Mark that we're back to viewing the list
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

if (exportJsonButton) {
  exportJsonButton.addEventListener('click', () => {
    if (currentViewedRun) {
      exportToJSON(currentViewedRun);
    } else {
      alert('No run data available to export');
    }
  });
}

if (batchExportButton) {
  batchExportButton.addEventListener('click', batchExportAllRuns);
}

if (generateInsightButton) {
  generateInsightButton.addEventListener('click', generateInsight);
}

if (compareModeToggle) {
  compareModeToggle.addEventListener('click', toggleCompareMode);
}

if (startComparisonButton) {
  startComparisonButton.addEventListener('click', startComparison);
}

if (backToListFromComparisonButton) {
  backToListFromComparisonButton.addEventListener('click', () => {
    comparisonViewer.classList.add('hidden');
    resultsList.parentElement.classList.remove('hidden');
    isViewingRun = false; // Mark that we're back to viewing the list
  });
}

// Query page insight generation
async function generateQueryInsight() {
  if (!currentQueryRun) {
    alert('No run data available to analyze. Please run a query first.');
    return;
  }

  try {
    // Get analyst model from input, or use default
    const analystModel = queryAnalystModelInput?.value?.trim() || 'x-ai/grok-4.1-fast:free';

    // Show loading state
    queryGenerateInsightButton.disabled = true;
    queryGenerateInsightButton.textContent = 'Generating...';
    queryInsightLoading.classList.remove('hidden');
    queryInsightResult.classList.add('hidden');

    const response = await fetch('/api/insight', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        runData: currentQueryRun,
        analystModel: analystModel
      })
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      const errorMessage = errorBody.error || 'Failed to generate insight.';
      throw new Error(errorMessage);
    }

    const result = await response.json();

    // Display the newly generated insight
    queryInsightLoading.classList.add('hidden');
    queryInsightResult.classList.remove('hidden');

    let insightHtml = '<div class="insight-header-card">';
    insightHtml += `<strong>✨ Insight Generated</strong><br>`;
    insightHtml += `<span class="insight-model-info">Analyst Model: ${escapeHtml(result.model)}</span>`;
    insightHtml += '</div>';
    insightHtml += '<div class="insight-content">';

    if (window.marked) {
      insightHtml += window.marked.parse(result.insight);
    } else {
      insightHtml += result.insight.replace(/\n/g, '<br/>');
    }

    insightHtml += '</div>';
    queryInsightResult.innerHTML = insightHtml;

    queryGenerateInsightButton.disabled = false;
    queryGenerateInsightButton.textContent = 'Generate Another Insight';

    // Update currentQueryRun with the insight (if it was saved to the run.json)
    if (currentQueryRun && currentQueryRun.runId) {
      try {
        const reloadResponse = await fetch(`/api/runs/${currentQueryRun.runId}`);
        if (reloadResponse.ok) {
          const updatedRunData = await reloadResponse.json();
          currentQueryRun = updatedRunData;
        }
      } catch (reloadError) {
        console.error('Error reloading run data:', reloadError);
        // Don't fail - insight was still generated
      }
    }
  } catch (error) {
    console.error('Error generating insight:', error);
    queryInsightLoading.classList.add('hidden');
    queryInsightResult.classList.remove('hidden');
    queryInsightResult.innerHTML = `<div class="error-message"><strong>Error:</strong> ${error.message}</div>`;
    queryGenerateInsightButton.disabled = false;
    queryGenerateInsightButton.textContent = 'Generate AI Insight Summary';
  }
}

if (queryGenerateInsightButton) {
  queryGenerateInsightButton.addEventListener('click', generateQueryInsight);
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
