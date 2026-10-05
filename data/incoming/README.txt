Drop real test-case exports here during the day — intern testing session
outputs, later real pilot session logs. Anything in this folder gets swept
into a dated data/logs/YYYY-MM-DD/ folder and committed once a day by the
GitHub Action, only if there's actually something new.

Do not put general medical reference content here — this folder is for
real test/pilot interaction data only. Protocol documents (IMNCI/NHM/WHO
CHW guidelines) get ingested once into the RAG layer separately, not fed
here daily.
