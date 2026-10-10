Hi Mehmet,

Thanks for joining the kickoff! Here is everything you need to start.

Hackathon page (task, scoring, rules, timeline):
[[Build the Builder  Freya × Y Combinator]]

Starter kit, version 3 (briefs, docs, 13 practice customers, an example agent and an example builder):
[[build-the-builder/README|build-the-builder]]
The kit has a version number in its file name and at the top of [[build-the-builder/README|README.md]] (see [[build-the-builder/VERSION|VERSION]]). If we update it, we will email you the new version.
Read [[build-the-builder/README|README.md]] first, it has a ten-minute start.

Your Freya API key:
Sign in at https://staging-app.freyavoice.ai and create a key in your workspace under API keys. Put it in env.sh as FREYA_API_KEY (copy from [[build-the-builder/env.example|env.example]]).

The bank's tool API:
The phone agent calls it during a call. Its description is in the kit at [[build-the-builder/tools/openapi.json|tools/openapi.json]]. You pick your own team key, any secret of 16 or more characters, and use the same one every time.

Starter workflow:
Your workspace already has "Freya Bank Collections Base". Its test variables hold a practice customer, so you can start a chat right away. The same agent is in the kit as [[build-the-builder/examples/base-agent.json|examples/base-agent.json]].

Kickoff recording:
[[transcript]]

Timeline:
Hidden briefs open on Sunday at 17:00 UTC (20:00 Istanbul).
Submissions close on Sunday at 20:00 UTC (23:00 Istanbul).
We will send the submission steps before the hidden briefs open.

Good to know:
- You can work solo or in a team of two.
- One practice simulation runs at a time per workspace.
- Any tool is fine for your builder: Claude Code, Codex, your own code. Keep the builder's trace, we ask for it with your submission.

Background reading, the benchmark that inspired this format:
[[𝜏𝜏-Bench An Environment for End-To-End, Realistic Agent Construction]]

Questions? Reply to this email and we will get back to you quickly.

Good luck!
Freya team

---

## Kit index

- build-the-builder/
	- [[build-the-builder/README|README.md]]
	- [[build-the-builder/VERSION|VERSION]]
	- [[build-the-builder/env.example|env.example]]
	- [[build-the-builder/freya.py|freya.py]]
	- [[build-the-builder/public-test-set.json|public-test-set.json]]
	- briefs/
		- [[build-the-builder/briefs/brief-a|brief-a.md]]
		- [[build-the-builder/briefs/brief-b|brief-b.md]]
	- docs/
		- [[build-the-builder/docs/api|api.md]]
		- [[build-the-builder/docs/tools-and-code|tools-and-code.md]]
		- [[build-the-builder/docs/workflow-format|workflow-format.md]]
	- examples/
		- [[build-the-builder/examples/agent_builder.py|agent_builder.py]]
		- [[build-the-builder/examples/base-agent.json|base-agent.json]]
	- tools/
		- [[build-the-builder/tools/openapi.json|openapi.json]]
		- [[build-the-builder/tools/run_cases.py|run_cases.py]]
		- [[build-the-builder/tools/score.py|score.py]]
	- .claude/skills/build-phone-agent/
		- [[build-the-builder/.claude/skills/build-phone-agent/SKILL|SKILL.md]] *(hidden folder — Obsidian not index dot-folders)*
