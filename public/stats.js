/**
 * Statistical Analysis Module for AI Ethics Comparator
 * Provides robust statistical functions for analyzing experimental runs
 */

/**
 * Chi-square test for comparing two categorical distributions
 * @param {Array} observed1 - Observed frequencies for group 1 [group1Count, group2Count, undecidedCount]
 * @param {Array} observed2 - Observed frequencies for group 2 [group1Count, group2Count, undecidedCount]
 * @returns {Object} - { chiSquare, pValue, degreesOfFreedom, significant }
 */
function chiSquareTest(observed1, observed2) {
  const n1 = observed1.reduce((a, b) => a + b, 0);
  const n2 = observed2.reduce((a, b) => a + b, 0);

  if (n1 === 0 || n2 === 0) {
    return null;
  }

  let chiSquare = 0;
  const k = observed1.length;

  for (let i = 0; i < k; i++) {
    const expected1 = (observed1[i] + observed2[i]) * n1 / (n1 + n2);
    const expected2 = (observed1[i] + observed2[i]) * n2 / (n1 + n2);

    if (expected1 > 0) {
      chiSquare += Math.pow(observed1[i] - expected1, 2) / expected1;
    }
    if (expected2 > 0) {
      chiSquare += Math.pow(observed2[i] - expected2, 2) / expected2;
    }
  }

  const df = k - 1;
  const pValue = chiSquareToPValue(chiSquare, df);

  return {
    chiSquare: chiSquare.toFixed(4),
    pValue: pValue.toFixed(4),
    degreesOfFreedom: df,
    significant: pValue < 0.05
  };
}

/**
 * Convert chi-square statistic to p-value
 * Uses approximation for degrees of freedom 1-10
 */
function chiSquareToPValue(chiSquare, df) {
  // Approximation using gamma function for common df values
  // For df=1, we can use normal approximation
  if (df === 1) {
    const z = Math.sqrt(chiSquare);
    return 2 * (1 - normalCDF(z));
  }

  // For df=2, exact formula
  if (df === 2) {
    return Math.exp(-chiSquare / 2);
  }

  // General approximation using Wilson-Hilferty transformation
  const k = df;
  const x = chiSquare;
  const z = Math.pow(x / k, 1/3) - (1 - 2/(9*k)) / Math.sqrt(2/(9*k));
  return 1 - normalCDF(z);
}

/**
 * Standard normal cumulative distribution function
 */
function normalCDF(z) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}

/**
 * Wilson confidence interval for a proportion
 * More accurate than normal approximation, especially for small samples or extreme proportions
 * @param {number} successes - Number of successes
 * @param {number} total - Total trials
 * @param {number} confidence - Confidence level (default 0.95 for 95% CI)
 * @returns {Object} - { proportion, lower, upper, marginOfError }
 */
function wilsonConfidenceInterval(successes, total, confidence = 0.95) {
  if (total === 0) {
    return { proportion: 0, lower: 0, upper: 0, marginOfError: 0 };
  }

  const p = successes / total;
  const z = getZScore(confidence);
  const z2 = z * z;

  const denominator = 1 + z2 / total;
  const center = (p + z2 / (2 * total)) / denominator;
  const margin = z * Math.sqrt((p * (1 - p) / total + z2 / (4 * total * total))) / denominator;

  return {
    proportion: parseFloat(p.toFixed(4)),
    lower: parseFloat(Math.max(0, center - margin).toFixed(4)),
    upper: parseFloat(Math.min(1, center + margin).toFixed(4)),
    marginOfError: parseFloat((margin * 2).toFixed(4))
  };
}

/**
 * Get z-score for confidence level
 */
function getZScore(confidence) {
  const confidenceMap = {
    0.90: 1.645,
    0.95: 1.96,
    0.99: 2.576,
    0.999: 3.291
  };
  return confidenceMap[confidence] || 1.96;
}

/**
 * Bootstrap confidence interval for consistency
 * Estimates variability in decision distribution through resampling
 * @param {Array} decisions - Array of decision values (1, 2, or null for undecided)
 * @param {number} bootstrapSamples - Number of bootstrap samples (default 1000)
 * @param {number} confidence - Confidence level (default 0.95)
 * @returns {Object} - { meanConsistency, lower, upper }
 */
function bootstrapConsistency(decisions, bootstrapSamples = 1000, confidence = 0.95) {
  if (decisions.length === 0) {
    return { meanConsistency: 0, lower: 0, upper: 0 };
  }

  const consistencyScores = [];

  for (let i = 0; i < bootstrapSamples; i++) {
    // Resample with replacement
    const sample = [];
    for (let j = 0; j < decisions.length; j++) {
      const randomIndex = Math.floor(Math.random() * decisions.length);
      sample.push(decisions[randomIndex]);
    }

    // Calculate consistency (proportion of most common decision)
    const counts = {};
    sample.forEach(d => {
      counts[d] = (counts[d] || 0) + 1;
    });

    const maxCount = Math.max(...Object.values(counts));
    const consistency = maxCount / sample.length;
    consistencyScores.push(consistency);
  }

  // Sort and find percentiles
  consistencyScores.sort((a, b) => a - b);
  const alpha = 1 - confidence;
  const lowerIndex = Math.floor(bootstrapSamples * alpha / 2);
  const upperIndex = Math.floor(bootstrapSamples * (1 - alpha / 2));

  const mean = consistencyScores.reduce((a, b) => a + b, 0) / consistencyScores.length;

  return {
    meanConsistency: parseFloat(mean.toFixed(4)),
    lower: parseFloat(consistencyScores[lowerIndex].toFixed(4)),
    upper: parseFloat(consistencyScores[upperIndex].toFixed(4))
  };
}

/**
 * Cohen's h effect size for comparing two proportions
 * Measures the magnitude of difference between two proportions
 * @param {number} p1 - Proportion 1
 * @param {number} p2 - Proportion 2
 * @returns {Object} - { h, interpretation }
 */
function cohensH(p1, p2) {
  // Arcsine transformation
  const phi1 = 2 * Math.asin(Math.sqrt(p1));
  const phi2 = 2 * Math.asin(Math.sqrt(p2));
  const h = Math.abs(phi1 - phi2);

  let interpretation = 'negligible';
  if (h >= 0.8) interpretation = 'large';
  else if (h >= 0.5) interpretation = 'medium';
  else if (h >= 0.2) interpretation = 'small';

  return {
    h: parseFloat(h.toFixed(4)),
    interpretation
  };
}

/**
 * Calculate inter-run effect size comparing two experimental runs
 * @param {Object} run1 - First run data with summary
 * @param {Object} run2 - Second run data with summary
 * @returns {Object} - Effect size metrics and interpretation
 */
function interRunEffectSize(run1, run2) {
  if (!run1.summary || !run2.summary) {
    return null;
  }

  // Calculate proportions for Group 1
  const p1 = (run1.summary.group1?.count || 0) / run1.summary.total;
  const p2 = (run2.summary.group1?.count || 0) / run2.summary.total;

  const effectSize = cohensH(p1, p2);
  const absoluteDifference = Math.abs(p1 - p2);

  return {
    run1Proportion: parseFloat(p1.toFixed(4)),
    run2Proportion: parseFloat(p2.toFixed(4)),
    absoluteDifference: parseFloat(absoluteDifference.toFixed(4)),
    cohensH: effectSize.h,
    interpretation: effectSize.interpretation,
    practicallySignificant: absoluteDifference >= 0.1 // 10% difference threshold
  };
}

/**
 * Comprehensive statistical summary for a single run
 * @param {Object} runData - Run data with responses
 * @returns {Object} - Complete statistical summary
 */
function comprehensiveStats(runData) {
  if (runData.paradoxType !== 'trolley') {
    return {
      type: 'open_ended',
      iterationCount: runData.iterationCount
    };
  }

  const decisions = runData.responses.map(r => r.group);
  const group1Count = runData.summary.group1?.count || 0;
  const group2Count = runData.summary.group2?.count || 0;
  const undecidedCount = runData.summary.undecided?.count || 0;
  const total = runData.summary.total;

  // Wilson confidence intervals for each decision type
  const group1CI = wilsonConfidenceInterval(group1Count, total);
  const group2CI = wilsonConfidenceInterval(group2Count, total);

  // Bootstrap consistency estimate
  const consistency = bootstrapConsistency(decisions);

  return {
    type: 'trolley',
    total: total,
    distributions: {
      group1: {
        count: group1Count,
        proportion: group1CI.proportion,
        confidenceInterval: {
          lower: group1CI.lower,
          upper: group1CI.upper,
          marginOfError: group1CI.marginOfError
        }
      },
      group2: {
        count: group2Count,
        proportion: group2CI.proportion,
        confidenceInterval: {
          lower: group2CI.lower,
          upper: group2CI.upper,
          marginOfError: group2CI.marginOfError
        }
      },
      undecided: {
        count: undecidedCount,
        proportion: parseFloat((undecidedCount / total).toFixed(4))
      }
    },
    consistency: consistency
  };
}

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    chiSquareTest,
    wilsonConfidenceInterval,
    bootstrapConsistency,
    cohensH,
    interRunEffectSize,
    comprehensiveStats
  };
}
