# Manual private-bucket integration check

Use synthetic files and a dedicated private bucket. This procedure is not part
of the automated tests and requires existing HF authentication with bucket write
access. Run it only when you intend to create that bucket and upload test data.

1. Create two temporary home directories representing devices A and B, with
   separate `XDG_CONFIG_HOME` directories. Set `HF_TOKEN` through your normal
   credential mechanism before changing `HOME`, so the HF client does not lose
   access to its usual credential cache. Do not copy your real session directories.
2. In device A's home, create files beneath `.codex/sessions/2026/10/`,
   `.codex/archived_sessions/`, and `.claude/projects/example/nested/`. Include a
   `.jsonl` file, a hidden file, and a binary file with known contents. Keep a copy
   of the synthetic fixture tree outside these source directories for comparison.
3. With device A's `HOME` and `XDG_CONFIG_HOME`, run
   `uv run hftracer init --bucket YOUR_USER/hftracer-integration`, then
   `uv run hftracer sync --dry-run`. Verify the plan lists the fixture uploads
   while the bucket stays empty. The `--preview` alias should produce the same
   plan. Run `uv run hftracer sync` to transfer the files.
   Verify the bucket is private and files appear under
   `devices/<device-A>/` with the expected agent and directory prefixes. There
   should be no hftracer metadata or manifest objects.
4. Run sync again without changing the fixture files. HF's sync summary should
   show no uploads and should report skipped files.
5. Modify an existing file (changing its size and modification time), add another,
   and delete a third locally. Run sync. Only the modified and new files should be
   uploaded; the locally deleted file must remain remotely.
6. Download `hf://buckets/YOUR_USER/hftracer-integration/devices/<device-A>/` into
   a separate temporary directory using `hf buckets sync`. Compare downloaded
   file bytes against the original fixture copy plus the modifications. Verify
   hidden files, binary contents, nested paths, and the retained deleted file.
7. Create a file at the same relative session path in device B's temporary home,
   using different contents. Initialize device B against the same bucket and sync.
   Verify its device ID differs from A's and both versions remain at their
   respective prefixes. Re-run A's init and confirm its namespace stays unchanged.
8. Optionally change the test bucket to public, then run sync and verify it fails
   before any upload. Restore it to private through HF before further testing.

Remove the temporary local directories when finished. Remote cleanup is manual;
hftracer never deletes the bucket or its files.
