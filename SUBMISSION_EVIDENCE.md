VOICEGUARD

==========



Core Guarantee:

Superseded work cannot become spoken reality.





REQUIREMENT              IMPLEMENTATION                  EVIDENCE

\--------------------------------------------------------------------------------------------------------------

Interruption                 VoiceGuard.on\_interrupt        		voiceguard/voiceguard.py

&#x20;                                                                             		Live interruption logs



Supersession                     request\_id fencing              		voiceguard/voiceguard.py

&#x09;		                                                        	 UI timeline

&#x20;                       			                                 	benchmark.py



Stale audio prevention    Per-chunk consistency firewall   	voiceguard/livekit\_agent.py

&#x20;                                                       			 	Stale Rime audio rejection logs

&#x20;                                                        				benchmark.py



Rime integration           coda / astra / WebSocket       	 	RIME\_EVIDENCE.md

&#x20;                                                        				scripts/rime\_preflight.py

&#x20;                                                        				Preflight PASSED output



Cancellation               asyncio.Task cancellation      		voiceguard/voiceguard.py

&#x20;                                                        				voiceguard/livekit\_agent.py

&#x20;                                                        				TOOL\_CANCELLED logs

&#x20;                                                        				benchmark.py



Reconciliation             Late completion fencing       		voiceguard/voiceguard.py

&#x20;                                                        				benchmark.py

&#x20;                                                        				72 late completions fenced



Reproducibility               benchmark.py                  		benchmark.py

&#x20;                                                        				100-trial benchmark output



Automated tests                    tests/                         			tests/

&#x20;                                                        				   21 passed



Live UI                               ui/                            				ui/

&#x20;                                                        				Live dashboard evidence





BENCHMARK EVIDENCE

=======================



Command:



python .\\benchmark.py --trials 100 --seed 42





Output:



VOICEGUARD BENCHMARK

======================================

Trials: 100

Seed: 42



Interrupted requests:       100

Stale speech leakage:       0

Stale chunks rejected:      510

Stale chunks played:        0

Tool cancellations:         42

Late completions fenced:    72



By phase:

&#x20; tool  trials=42  rejected=0    fenced=42

&#x20; llm   trials=30  rejected=0    fenced=30

&#x20; tts   trials=28  rejected=510  fenced=0



PASS: no stale audio reached playback





AUTOMATED TEST EVIDENCE

============================



Command:



pytest -q



Result:



21 passed





LIVE INTERRUPTION EVIDENCE

============================



Strongest demonstrated case:



Request 11:

"My friends from Bombay to Delhi."



Tool started:



VOICEGUARD: TOOL\_STARTED request=11 delay=5.00s



User interrupted:



VOICEGUARD: committing interruption source=user\_state\_changed old\_request=11 state=TOOL\_RUNNING

VOICEGUARD: interruption committed old\_request=11



Updated user request:



"Actually, Chennai is the problem."



New request:



VOICEGUARD REQUEST: id=12 text='Actually, Chennai is the problem.'



Old request cancellation:



VOICEGUARD: TOOL\_CANCELLED request=11



New Rime stream:



VOICEGUARD RIME: stream requested request\_id=12 active\_id=12





STALE AUDIO EVIDENCE

=========================



A stale Rime audio chunk was rejected after supersession.



Example:



VOICEGUARD RIME: stale audio rejected sequence=35



Benchmark confirms:



Stale speech leakage: 0

Stale chunks played: 0

Stale chunks rejected: 510





RIME INTEGRATION EVIDENCE

=============================



Model:

coda



Speaker:

astra



Transport:

WebSocket



Segmentation:

immediate



Sample rate:

22050 Hz



Prewarm:

Enabled



Preflight:

scripts/rime\_preflight.py



Expected preflight result:



PASSED





CANCELLATION AND RECONCILIATION

====================================



Tool cancellations:

42



Late completions fenced:

72



This demonstrates that superseded background work cannot later become

spoken output.





LIVE UI EVIDENCE

=================



The dashboard provides visible evidence for:



\- Current request

\- Request ID

\- State transitions

\- Listening

\- Thinking

\- Tool running

\- Responding

\- Superseded requests

\- Ghost tasks

\- Generated audio chunks

\- Actually played audio chunks

\- Stale audio blocked

\- Replacement request

\- Timeline events

\- Relative timestamps

\- Reason for blocked output





ARCHITECTURE EVIDENCE

=========================



Core VoiceGuard logic:



voiceguard/voiceguard.py



LiveKit integration:



voiceguard/livekit\_agent.py



Important architectural separation:



voiceguard.py contains ZERO LiveKit imports.



LiveKit is responsible for transport/audio interruption.



VoiceGuard independently handles:



\- request versioning

\- interruption state

\- task cancellation

\- stale-result fencing

\- stale-audio rejection

\- reconciliation





REPOSITORY EVIDENCE MAP

===========================



voiceguard/

&#x20;   Core VoiceGuard logic

&#x20;   LiveKit integration

&#x20;   Rime TTS integration



tests/

&#x20;   Automated correctness tests



benchmark.py

&#x20;   Reproducible 100-trial benchmark



scripts/rime\_preflight.py

&#x20;   Rime catalog/configuration verification



ui/

&#x20;   Live dashboard



README.md

&#x20;   Setup, architecture and project documentation



RIME\_EVIDENCE.md

&#x20;   Rime integration and runtime evidence





CORE GUARANTEE

===================



Superseded work cannot become spoken reality.



The system tracks:



1\. What the user requested.

2\. Which request is currently active.

3\. Which background work belongs to each request.

4\. Which generated audio belongs to each request.

5\. Which audio chunks actually reached playback.



When the user changes their request:



\- The previous request becomes superseded.

\- In-flight work is cancelled where possible.

\- Late results are fenced.

\- Stale LLM output is rejected.

\- Stale Rime audio is rejected per chunk.

\- Only audio belonging to the active request can reach playback.





EVIDENCE BOUNDARIES

========================



Do not claim metrics that were not measured.



Verified benchmark claims:



\- 100 trials

\- 100 interrupted requests

\- 0 stale speech leakage

\- 510 stale chunks rejected

\- 0 stale chunks played

\- 42 tool cancellations

\- 72 late completions fenced

\- PASS: no stale audio reached playback



Do not claim median/p95 latency unless a new benchmark explicitly measures it.
