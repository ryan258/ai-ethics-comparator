# State ownership

Services belong to the application lifespan and are injected into core logic. Run tasks, provider semaphores, analysis deduplication, and storage locks belong to those service instances. The supported deployment has one process.

- `RunStorage` reserves identities and atomically writes snapshots. Its bounded metadata cache invalidates on file stat changes. Reads validate records without migrating their evidence.
- `ExperimentStorage` serializes claims and updates. Manifests retain condition identities and reconcile linked run states; the active execution marker prevents a partly finished matrix from being offered as stopped work.
- `QueryProcessor` limits active iterations; `AIService` separately limits all provider calls, including analysis and rubric scoring. No path may bypass the provider adapter's semaphore.
- `AnalysisEngine` shares identical in-flight evidence/model operations. Completed tasks are removed; shutdown cancels and drains them.
- Run snapshot persistence remains inside the per-run state lock so older snapshots cannot arrive after newer ones. Undecided terminal responses are immutable across resume.
- Scenario and prompt-template caches persist for the process lifetime. Restart after changing their files. Consumers receive copied scenario data.
- Configuration is read at startup. Provider structured-output capability caching is advisory and resets on restart.

No module-level service singleton may import or depend on application state. Existing bounded immutable-data caches are explicit exceptions to the general preference against mutable globals.
