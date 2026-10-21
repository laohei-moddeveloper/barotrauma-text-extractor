# AbyssText repository

Use Python 3.12+; runtime code is standard library only. Keep this project separate from BaroDock and other mods.
Run `python -m unittest discover -s tests -v`. A missing Windows symbolic-link privilege must be reported as a skip, not a successful integration check.
Build Windows with `build-windows.ps1`; generated EXE, local publish state, credentials and third-party mod contents stay out of Git.
The scanner must remain read-only and must not execute source scripts. Test with isolated fixtures. Never launch Barotrauma to validate this external utility.
Commit and push useful cloud-task results to the task branch on origin. Workshop publication and GitHub Release are separate from source synchronization. Never reuse another project's Workshop item ID.
