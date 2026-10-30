# RTL and self-checking TB decisions

Read the actual module before choosing a template. A combinational packer, an event counter and a stalled stream have different latency and reset contracts.

## RTL

- Explicitly extend operands BEFORE addition/subtraction; assigning a narrow intermediate to a wide output does not recover discarded bits. Signed inputs do not make every concatenation or mixed expression signed.
- Write rounding/truncation/saturation or wrap semantics in the contract; test zero, extrema and values on both sides of the transition. Do not add rounding to an existing bit-exact contract without approval.
- Every combinational output/next-state receives a value on all paths; sequential state updates use nonblocking assignments. Reset priority, enable and clear/event collision behavior must be observable tests, not coding-style assumptions.
- Ready/valid acceptance is valid AND ready at the sampling edge. A one-slot registered stage may accept when empty OR when its old output is accepted. While stalled, valid and payload stay stable. Do not increment IDs on valid alone or discard old output when accepting a replacement.
- Parameter boundary cases can cause zero-width slices/replications or signed shifts. Validate supported widths and use appropriately sized literals. The elastic example supports WIDTH >= 1; it is not a CDC FIFO or a timing-isolating ready register.

## Testbench

- Compute reference values from mathematical meaning or another independently justified implementation. For sign extension, interpret the source as a signed integer and compare its full destination word; do not copy the DUT replication expression.
- Drive on a falling edge and check pre-update outputs at the next rising edge, or document another race-free scheme. Check reset values after NBA updates. Arbitrary extra delays must not hide an off-by-one cycle.
- A stream scoreboard contains accepted transactions. Compare the old output before inserting a newly accepted input for a registered stage; a zero-latency module needs a different ordering. Reset discards queued work only if the contract says so.
- Transaction order alone does not verify latency or capacity. At the sampling edge and after NBA, compare valid and any valid payload with the queue occupancy required by the contract, including while stalled. Bound in-flight transactions to the contracted capacity and account for consumed and reset-discarded transactions. A deeper pipeline can otherwise pass ordered comparisons and a generous final drain.
- Maintain stable input while the producer is stalled. Verify output hold, simultaneous consume/replace, idle gaps, reset with pending output, and draining. Include a directed full-rate section: random traffic alone can miss a throughput loss.
- Use case inequality (`!==`) for RTL comparisons that must reject X/Z. Count actual checks and report the first mismatch with enough state to replay it.
- Do not accept `$finish`, exit code 0, an old PASS log, or a PASS string printed before a later fatal as proof. The runner uses a fresh directory, requires an exact final marker and positive counts, and checks tool errors separately.

## Scope of synthesis guidance

If the user asks for synthesis/timing, use the actual part and constraints in a separate approved flow; report tool/version, utilization, unconstrained paths and setup/hold results. Do not add false/multicycle paths simply to turn slack green. This Skill's runner performs behavioral simulation only: it does not emit an XDC, change a BD, program a board, or certify resource feasibility.
