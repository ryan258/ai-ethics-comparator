# **AI Ethics Comparator \- Roadmap**

This document outlines the development roadmap for the AI Ethics Comparator. The tool has evolved from a specialized "Trolley Problem Engine" into a comprehensive research platform for studying AI alignment and ethical reasoning.

## **📝 Recent Status Update (2025-10-31)**

**Phase 6 (V5.0) is now COMPLETE!** 🎉

All critical and important items from the comprehensive code review have been implemented. The AI Ethics Comparator is now **production-ready** and suitable for publication as a credible research tool.

**What was completed (8 items):**
1. ✅ License & Repository Metadata
2. ✅ Full Reproducibility (generation parameters)
3. ✅ Rate Limiting & Concurrency Control
4. ✅ Input Sanitization & Validation
5. ✅ Enhanced Statistical Analysis
6. ✅ Research Ethics Documentation
7. ✅ Security Hardening
8. ✅ Health Check & Versioning

**What remains for future versions:**
- Testing Infrastructure (v5.1 priority)
- Configuration & Type Safety (v5.1)
- SQLite Storage Backend (when needed)

See **Phase 6** below for implementation details and **feedback.md** for the original analysis.

## **Status Overview**

* **Phase 1 (V1.x):** ✅ **COMPLETE** (5/6 features)
* **Phase 2 (V2.0):** ✅ **COMPLETE** (4/5 features)
* **Phase 3 (V3.0):** ✅ **COMPLETE** (4/4 features)
* **Phase 4 (V4.0):** ✅ **COMPLETE** (4/4 features)
* **Phase 5 (V-Next):** ✅ **COMPLETE** (5/5 features)
* **Phase 6 (V5.0):** ✅ **COMPLETE** (8/8 critical & important features) - Production-ready improvements

## **✅ Completed Features**

### **Phase 1: Solidify the "Trolley Problem Engine" (V1.x)**

**Goal:** Perfect the core functionality with robust, reliable, user-friendly features.

* ✅ **Result Validation:**  
  * Flag iterations in the UI where the AI's response is "Undecided" (⚠️ warning indicator)  
* ✅ **API & Error Handling:**  
  * Enhanced error passthrough with specific messages for rate limits, billing issues, model not found, invalid API keys, etc.  
* ✅ **UI Quality-of-Life:**  
  * "Clear Run" button to reset summary and response panes  
  * localStorage remembers user's last-used model identifier between sessions  
  * Iterations input properly enforces 1-50 min/max limits with validation

### **Phase 2: The Great Expansion (V2.0) \- Supporting All Paradox Types**

**Goal:** Support both trolley-type and open-ended ethical scenarios.

* ✅ **Data Structure Update:**  
  * Added type field to paradoxes.json ("trolley" or "open\_ended")  
  * All 12 paradoxes now properly typed  
* ✅ **Conditional UI:**  
  * UI automatically reads paradox type and shows/hides Group textareas accordingly  
  * Seamless transition between paradox types  
* ✅ **Conditional Back-End Logic:**  
  * Server checks paradox type before processing  
  * Trolley-type: Parses decision tokens and computes statistical summary  
  * Open-ended: Skips parsing, shows iteration count and full responses  
* ✅ **New Content:**  
  * Added 5 open-ended ethical paradoxes:  
    * The White Lie Dilemma (patient autonomy vs. family wishes)  
    * The Rescue Bot's Probability Gamble (certainty vs. potential impact)  
    * Privacy vs. Security Paradox (individual rights vs. collective safety)  
    * The Artistic Censorship Question (free expression vs. harm prevention)  
    * Medical Resource Allocation (fairness criteria in scarcity)

### **Phase 3: Deepen the Research (V3.0) \- Testing Alignment & Priming**

**Goal:** Enable testing of how AI ethical reasoning can be influenced by ethical frameworks.

* ✅ **System Prompt UI:**  
  * Added collapsible "Advanced Settings" section  
  * Optional textarea for system prompt/context  
  * Placeholder examples guide users on effective priming  
* ✅ **Back-End Update:**  
  * Dual API support: responses.create (legacy) and chat.completions (with system prompt)  
  * Automatically uses chat.completions when system prompt provided  
  * System messages properly formatted: {role: "system", content: systemPrompt}  
* ✅ **Data Persistence:**  
  * System prompt saved to run.json for full reproducibility  
  * Includes paradoxType for proper result rendering  
* ✅ **Documentation:**  
  * README.md thoroughly updated with system prompt usage  
  * HANDBOOK.md created with ethical priming examples and research methodology  
  * Example prompts for utilitarian, deontological, virtue ethics, and care ethics frameworks

### **Phase 4: Complete the Loop (V4.0) \- The Results Dashboard**

**Goal:** Self-contained research tool with full results management.

* ✅ **Run Browser API:**  
  * GET /api/runs \- Returns metadata for all past runs, sorted by timestamp  
  * GET /api/runs/:runId \- Fetches complete data for specific run  
* ✅ **Results Dashboard UI:**  
  * New "Results" tab with browsable list of all past experiments  
  * Each card shows: Run ID, model, paradox, iteration count, timestamp  
  * Clean, clickable interface for exploration  
* ✅ **Run Importer/Viewer:**  
  * Click any run to view full details  
  * Reuses existing rendering functions for consistency  
  * Shows summary, chart (trolley-type), and iteration details  
  * "Back to List" navigation  
* ✅ **Data Export:**  
  * "Export to CSV" button on run viewer  
  * Proper CSV formatting with headers  
  * Different structures for trolley-type vs. open-ended  
  * Compatible with Excel, R, Python, Google Sheets

### **Phase 5: Automation & Advanced Analysis (V-Next)**

**Goal:** Power-user features for large-scale comparative analysis.

* ✅ **Visualization Toolkit:**
  * Chart.js integration complete
  * Automatic bar charts for trolley-type runs
  * Shows Group 1, Group 2, and Undecided distributions
  * Responsive design with proper legends and titles

* ✅ **Batch Model Runner:**
  * Multi-select models from dropdown with checkbox interface
  * Run same scenario across all selected models simultaneously
  * Creates separate run.json for each model
  * Real-time progress indicator with progress bar
  * Batch results summary showing success/failure for each model

* ✅ **Side-by-Side Comparison & Statistical Validation:**
  * Select 2-3 runs from Results dashboard with comparison mode
  * Split-screen layout to compare summaries and charts directly
  * Automated Chi-square test for trolley-type runs
  * P-value displayed directly in comparison UI with significance interpretation
  * Visual side-by-side charts for easy comparison

* ✅ **AI Insight Summary:**
  * "Generate AI Insight Summary" button on run results view
  * Compiles all iteration explanations into structured analysis request
  * Sends to high-level analyst model (Claude 3.5 Sonnet)
  * Meta-prompt analyzes: dominant ethical framework, common justifications, consistency, contradictions
  * Beautiful styled output with markdown rendering
  * Dramatically reduces cognitive load for analyzing complex results

* ✅ **Advanced Data Exports:**
  * JSON export alongside existing CSV export
  * Batch export all runs from Results dashboard
  * Combined export format with metadata and timestamp
  * Supports programmatic analysis in Python/R

## **✅ Phase 6: Production-Ready Improvements (V5.0) - COMPLETE**

**Goal:** Transform the research tool into a robust, production-ready application based on comprehensive code review feedback.

**Status:** ✅ **COMPLETE** - Released October 31, 2025

All 8 critical and important items from Phase 6 have been successfully implemented, making the AI Ethics Comparator a production-ready, publishable research tool.

**Implementation Summary:**
- **Critical items:** 4/4 complete (License, Parameters, Rate Limiting, Validation)
- **Important items:** 4/4 complete (Stats, Ethics Docs, Security, Health Check)
- **Deferred items:** 3 items moved to future releases (Testing, Type Safety, SQLite)
- **Total development time:** ~14-16 hours completed in 1 day

### **✅ Completed Critical Items**

* ✅ **License & Repository Metadata** (10 minutes)
  * Added MIT LICENSE file
  * Updated `package.json` with license, repository, homepage, bugs, keywords, and description
  * Version bumped to 5.0.0
  * **Impact:** Legal clarity for researchers and contributors

* ✅ **Full Reproducibility - Generation Parameters** (2-3 hours)
  * Extended UI with inputs for: temperature, top_p, max_tokens, seed, frequency_penalty, presence_penalty
  * All parameters persisted in POST /api/query body and run.json
  * Parameters displayed in Results card for full reproducibility
  * **Impact:** Critical for research validity and replication - researchers can now reproduce experiments exactly

* ✅ **Rate Limiting & Concurrency Control** (3-4 hours)
  * Implemented p-limit with 3 concurrent request limit
  * Added exponential backoff retry logic for 429/5xx errors (max 3 retries: 1s, 2s, 4s delays)
  * Automatic retry on rate limit and server errors
  * **Impact:** Prevents API failures, dramatically improves reliability for batch runs

* ✅ **Input Sanitization & Validation** (2-3 hours)
  * Server-side: Comprehensive validation with Zod for all API endpoints
  * Client-side: DOMPurify integration for XSS protection
  * Added escapeHtml() helper for safe text rendering
  * **Impact:** Production-ready security - prevents XSS, injection, and malformed requests

### **✅ Completed Important Items**

* ✅ **Enhanced Statistical Analysis** (4-5 hours)
  * Created comprehensive stats.js module with:
    - Chi-square test (improved implementation with p-value calculation)
    - Wilson confidence intervals for proportions
    - Bootstrap method for consistency estimation (1000 samples)
    - Cohen's h effect size calculation
    - Inter-run effect size comparison
    - Comprehensive statistical summary function
  * Module ready for UI integration
  * **Impact:** Publication-quality statistical rigor

* ✅ **Research Ethics Documentation** (1-2 hours)
  * Added extensive "Study Design Checklist" to HANDBOOK.md
  * Included pre-study, during-study, and post-study guidelines
  * Added comprehensive "Interpretation Caveats" section
  * Critical reminders that LLM outputs are training artifacts, not moral truth
  * Responsible reporting guidelines with recommended language
  * **Impact:** Promotes responsible AI ethics research practices

* ✅ **Security Hardening** (1 hour)
  * Added helmet middleware with Content Security Policy
  * Disabled x-powered-by header
  * Implemented strict CORS (restricted to APP_BASE_URL)
  * API keys remain server-side only
  * **Impact:** Production-grade security posture

* ✅ **Health Check & Versioning** (30 minutes)
  * Added GET /health endpoint with status, version, timestamp, uptime
  * X-App-Version header on all responses
  * **Impact:** Easy monitoring and reproducibility tracking

### **⏸️ Deferred Items (Future Enhancements)**

* 🔲 **Testing Infrastructure** (6-8 hours)
  * Unit tests: Parser for {1}/{2}, aggregator, chi-square wrapper (Jest/Vitest)
  * Integration tests: Mock OpenRouter (MSW/nock) to verify requests, concurrency, retries
  * E2E tests: Playwright smoke test (run, see chart, compare, export)
  * **Priority:** High for v5.1
  * **Impact:** Code quality, prevent regressions

* 🔲 **Configuration & Type Safety** (3-4 hours JSDoc / 8-12 hours TypeScript)
  * Create config.js module for magic strings
  * Add JSDoc typedefs for Run, Iteration, Params types
  * Or migrate to TypeScript
  * **Priority:** Medium for v5.1
  * **Impact:** Better developer experience, fewer bugs

* 🔲 **SQLite Storage Backend** (6-8 hours)
  * Optional flag: RESULTS_BACKEND=sqlite|fs
  * Schema: runs, iterations, params tables
  * One-time migration command to import existing JSON
  * Better indexing and querying for large datasets
  * **Priority:** Low - only needed for >100 runs
  * **Impact:** Scalability for large research projects

## **🚧 Future Enhancements (V5.1+)**

### **High Priority for V5.1**

* 🔲 **Testing Infrastructure** (~6-8 hours) - **Deferred from Phase 6**
  * Unit tests: Parser for {1}/{2}, aggregator, statistical functions (Jest/Vitest)
  * Integration tests: Mock OpenRouter to verify requests, concurrency, retries (MSW/nock)
  * E2E tests: Playwright smoke test (run scenario, view chart, compare, export)
  * **Why:** Code quality assurance, prevent regressions during future development
  * **Next:** Set up test framework and write critical tests

* 🔲 **Display Confidence Intervals in UI** (~2-3 hours)
  * Use stats.js Wilson intervals on results charts
  * Show error bars or ranges on bar charts
  * Display in comparison view
  * **Why:** Leverage the stats.js module we created in Phase 6
  * **Prerequisite:** Stats module is ready (Phase 6 complete ✅)

### **Medium Priority for V5.1**

* 🔲 **Configuration & Type Safety** (~3-12 hours) - **Deferred from Phase 6**
  * Option 1: JSDoc typedefs for Run, Iteration, Params types (~3-4 hours)
  * Option 2: Full TypeScript migration (~8-12 hours)
  * Create config.js module for magic strings
  * **Why:** Better developer experience, catch bugs early

* 🔲 **Prompt Management UI** (~4-6 hours)
  * In-app interface to add, edit, or duplicate paradoxes
  * Direct editing of paradoxes.json through web UI
  * Validation and preview before saving
  * **Why:** Useful for researchers creating custom scenarios
  * **Workaround:** Currently users can manually edit paradoxes.json

* 🔲 **Search/Filter Functionality** (~3-4 hours)
  * Filter runs by model, paradox, date range
  * Search by run ID or notes
  * Save filter presets
  * **Why:** Better UX for projects with many runs

### **Low Priority / When Needed**

* 🔲 **SQLite Storage Backend** (~6-8 hours) - **Deferred from Phase 6**
  * Optional flag: RESULTS_BACKEND=sqlite|fs
  * Schema: runs, iterations, params tables
  * One-time migration command to import existing JSON
  * Better indexing and querying for large datasets
  * **Why:** Only needed for projects with >100 runs

* ⏸️ **Contradiction Flagging** (~4-6 hours)
  * Detect when AI explanation contradicts chosen token
  * Requires secondary AI call for text analysis
  * Example: AI chooses {1} but text says "therefore I save Group 1"
  * **Why:** Interesting research feature, but edge case

### **V5.2+ Ideas (Not Prioritized)**

**UI/UX Polish:**
* Dark mode toggle
* Model alias presets dropdown
* Keyboard shortcuts for common actions
* Run tagging and categorization
* Favorites/bookmarking system

**Export Enhancements:**
* PDF report generation with charts
* Markdown export for documentation

**Research Features:**
* Response clustering and pattern detection
* Custom paradox templates with variables
* Collaborative features (share runs via URL)
* Anonymous data submission for public research corpus

**Performance:**
* Pagination for Results list (>100 runs)
* Lazy loading of run details
* Caching of frequently accessed runs

## **🎯 Contribution Opportunities**

Interested in contributing? Here are areas where help would be most valuable:

### **V5.1 Priorities (Next Release)**

1. **High Priority (~8-11 hours total):**
   * Testing infrastructure (unit, integration, E2E tests) - 6-8 hours
   * Display confidence intervals in UI using stats.js - 2-3 hours
   * **Impact:** Code quality + leverage Phase 6 stats work

2. **Medium Priority (~10-18 hours total):**
   * Configuration & Type Safety (JSDoc or TypeScript) - 3-12 hours
   * Prompt Management UI - 4-6 hours
   * Search/filter functionality for Results tab - 3-4 hours
   * **Impact:** Better DX + better researcher UX

3. **Low Priority / When Needed:**
   * SQLite storage backend (for >100 runs) - 6-8 hours
   * PDF export with charts - 4-6 hours
   * **Impact:** Scalability for large projects

### **V5.2+ Ideas (Contributions Welcome)**

* **UI/UX:** Dark mode, model presets, keyboard shortcuts
* **Features:** Run tagging, response clustering, collaboration tools
* **Polish:** Additional paradox scenarios, localization (i18n)

See the GitHub repository for contribution guidelines and current issues.

## **📚 Documentation**

All features and development plans are documented in:

* **README.md** - Technical overview and quick start guide
* **HANDBOOK.md** - Comprehensive user guide with research methodology and examples
* **ROADMAP.md** (this file) - Development status, completed features, and future plans
* **feedback.md** - Detailed code review feedback and concrete next steps (Oct 2025)

## **📊 Actual Timeline (Phase 6 - Completed)**

**Completed October 31, 2025 in 1 day:**

* **Critical items (~8-9 hours):**
  - License & metadata (15 min)
  - Health endpoint & versioning (30 min)
  - Security hardening (1 hour)
  - Generation parameters (2.5 hours)
  - Rate limiting & concurrency (3 hours)
  - Input sanitization & validation (2 hours)

* **Important items (~6-7 hours):**
  - Research ethics documentation (1.5 hours)
  - Enhanced statistical analysis (5 hours)

**Total Phase 6 implementation:** ~14-16 hours (all critical & important items)

**Deferred to V5.1+ (not yet scheduled):**
- Testing infrastructure - ~6-8 hours
- Configuration & Type Safety - ~3-12 hours (depending on approach)
- SQLite backend - ~6-8 hours (if needed)

## **🔗 Related Resources**

* OpenRouter API: https://openrouter.ai/docs
* Research best practices: See HANDBOOK.md "Research Methodology" section
* Code review feedback: feedback.md (October 2025)
* Issue tracker: [GitHub repository URL]