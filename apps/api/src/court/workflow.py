"""The narrative path as a Microsoft Agent Framework workflow.

    alert -> narrator -> critic --approved------------------------> localizer -> Cue
                  ^         |----rejected, rewritable, budget left -> narrator
                  |         '----otherwise--------------------------> spike -> Spiked
                  '-- rewrite with the Critic's reasons

One run per alert. The Critic yields every rejection as an output, so refusals are
first-class artifacts in the stream rather than lines in a log.
"""

import inspect

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler

from match_events import minute_label

from .contracts import Alert, Claim, Cue, RejectionNotice, Spiked, Verdict
from .critic import Critic
from .localizer import Localizer
from .narrator import Narrator
from .state import MatchState


class NarratorExecutor(Executor):
    def __init__(self, narrator: Narrator, state: MatchState) -> None:
        super().__init__(id="narrator")
        self._narrator, self._state = narrator, state

    @handler
    async def on_alert(self, alert: Alert, ctx: WorkflowContext[Claim]) -> None:
        await ctx.send_message(await _settled(self._narrator.draft(alert, self._state)))

    @handler
    async def on_rejection(self, verdict: Verdict, ctx: WorkflowContext[Claim]) -> None:
        await ctx.send_message(await _settled(self._narrator.rewrite(verdict, self._state)))


async def _settled(claim):
    """The template narrator answers at once; a model-backed one answers when awaited."""
    return await claim if inspect.isawaitable(claim) else claim


class CriticExecutor(Executor):
    def __init__(self, critic: Critic, state: MatchState) -> None:
        super().__init__(id="critic")
        self._critic, self._state = critic, state

    @handler
    async def on_claim(self, claim: Claim, ctx: WorkflowContext[Verdict, RejectionNotice]) -> None:
        verdict = self._critic.review(claim, self._state)
        if not verdict.approved:
            await ctx.yield_output(
                RejectionNotice(
                    minute=minute_label(claim.t, claim.period),
                    claim=claim,
                    reasons=verdict.reasons,
                )
            )
        await ctx.send_message(verdict)


class LocalizerExecutor(Executor):
    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="localizer")
        self._localizer = localizer

    @handler
    async def on_approved(self, verdict: Verdict, ctx: WorkflowContext[None, Cue]) -> None:
        await ctx.yield_output(await self._localizer.render(verdict))


class SpikeExecutor(Executor):
    def __init__(self) -> None:
        super().__init__(id="spike")

    @handler
    async def on_dead(self, verdict: Verdict, ctx: WorkflowContext[None, Spiked]) -> None:
        claim = verdict.claim
        await ctx.yield_output(
            Spiked(minute=minute_label(claim.t, claim.period), claim=claim, reasons=verdict.reasons)
        )


def build_narrative_workflow(
    *,
    narrator: Narrator,
    critic: Critic,
    localizer: Localizer,
    state: MatchState,
    max_attempts: int = 3,
) -> Workflow:
    n = NarratorExecutor(narrator, state)
    c = CriticExecutor(critic, state)
    loc = LocalizerExecutor(localizer)
    spike = SpikeExecutor()

    def retry(v: Verdict) -> bool:
        return not v.approved and v.rewritable and v.claim.attempt < max_attempts

    def dead(v: Verdict) -> bool:
        return not v.approved and not retry(v)

    return (
        WorkflowBuilder(
            name="narrative",
            description="Narrator drafts, Critic verifies, Localizer renders",
            start_executor=n,
            max_iterations=4 * max_attempts + 4,
            output_from="all",
        )
        .add_edge(n, c)
        .add_edge(c, loc, condition=lambda v: v.approved)
        .add_edge(c, n, condition=retry)
        .add_edge(c, spike, condition=dead)
        .build()
    )
