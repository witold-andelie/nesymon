# Theory: definitions, lemmas and proofs

Draft for Section 5 and the appendix of the paper. Every statement below is exercised by a test in
`tests/test_core.py`; the tests are a sanity check, not a substitute for the proofs.

## 1. Setting

**Rule automaton.** A rule is a DFA $A=(Q,\Sigma,\delta,q_0,F)$ over a finite alphabet
$\Sigma\subseteq\{0,1\}^{AP}$ of mutually exclusive step types, with $\delta$ total on $Q\times\Sigma$.
Write $\delta(S,L)=\{\delta(q,\sigma): q\in S,\ \sigma\in L\}$. Let

- $D=\{q : \text{no word leads from } q \text{ into } F\}$ (dead states),
- $Z=\{q : \text{every state reachable from } q \text{ is in } F\}$ (sinks).

Both are closed under $\delta$, $D\cap F=\emptyset$ and $Z\subseteq F$.

**Trace and truth.** A trajectory has true letters $\sigma^*_1,\dots,\sigma^*_T\in\Sigma$, true run
$q^*_0=q_0$, $q^*_t=\delta(q^*_{t-1},\sigma^*_t)$, and true verdict $v^*=\textsf{compliant}$ if
$q^*_T\in F$, else $\textsf{violation}$.

**Observations.** At step $t$ each proposition $a$ is either *exact* (structured, or linguistic but
off its site, hence false by construction) or *judged*: the labeler returns $p_t(a)\in[0,1]$. Put
$\hat v_t(a)=\mathbb 1[p_t(a)\ge 1/2]$ and let $c_t(a)=\max(p_t(a),1-p_t(a))$ be the labeler's confidence.

**Assumption S (structure).** Exact propositions equal their true value. At each step at most one
proposition $a_t$ of the rule is judged, and flipping $a_t$ in $\sigma^*_t$ yields a letter of $\Sigma$.

Assumption S holds for every rule in `rules/dfas.py`: structured propositions are read from the
tool-call log, each linguistic proposition has one site kind, and the site kinds of the linguistic
propositions of one rule are disjoint.

**Value sets.** For a threshold $\tau\in[0,1]$, the value set of an exact proposition is its true
value, and for the judged proposition

$$C_t(a;\tau)=\{\hat v_t(a)\}\ \cup\ \{1-\hat v_t(a) : c_t(a)\le\tau\}.$$

This equals the conformal form $\{v : 1-p_t(a{=}v)\le\tau\}$ with the argmax as fallback when that set
is empty. So $\tau$ is a confidence gate: a judgement is widened to $\{0,1\}$ exactly when the
labeler's confidence is at most $\tau$, and every $\tau<1/2$ gives the hard-label monitor.

**Monitor.** $L_t(\tau)=\big(\prod_a C_t(a;\tau)\big)\cap\Sigma$, $S_0=\{q_0\}$,
$S_t(\tau)=\delta(S_{t-1}(\tau),L_t(\tau))$. The monitor stops with $\textsf{violation}$ at the first
$t$ with $S_t\subseteq D$, with $\textsf{compliant}$ at the first $t$ with $S_t\subseteq Z$, and
otherwise at $T$ outputs

$$V(S_T)=\begin{cases}\textsf{compliant} & S_T\subseteq F\\ \textsf{violation} & S_T\cap F=\emptyset\\ \textsf{abstain} & \text{otherwise.}\end{cases}$$

Write $v(\tau)$ for the output.

**Losses** for one (trajectory, rule) pair:

- verdict loss $\ell_{\rm ver}(\tau)=\mathbb 1[v(\tau)\notin\{\textsf{abstain},v^*\}]$, split into
  $\ell_{\rm miss}(\tau)=\mathbb 1[v^*=\textsf{violation},\ v(\tau)=\textsf{compliant}]$ and
  $\ell_{\rm fa}(\tau)=\mathbb 1[v^*=\textsf{compliant},\ v(\tau)=\textsf{violation}]$;
- full-coverage loss $\ell_{\rm cov}(\tau)=\mathbb 1[\exists t,a:\ \sigma^*_t(a)\notin C_t(a;\tau)]$;
- state-relevant coverage loss $\ell_{\rm sr}(\tau)$: the same, restricted to propositions relevant at
  the true state $q^*_{t-1}$, where $a$ is *relevant at* $q$ if some $\sigma,\sigma'\in\Sigma$ differing
  only in $a$ have $\delta(q,\sigma)\ne\delta(q,\sigma')$.

## 2. Structural lemmas

**Lemma 0 (well-definedness; early stopping is harmless).** Under Assumption S, $S_t(\tau)\neq\emptyset$
for all $t,\tau$, and $v(\tau)=V(S_T(\tau))$, where $S_T$ is obtained by continuing the propagation
after an early stop.

*Proof.* The letter that takes the true value on exact propositions and $\hat v_t(a_t)$ on the judged
one is $\sigma^*_t$ or its flip in $a_t$; both are in $\Sigma$ by Assumption S, so $L_t(\tau)\ne\emptyset$
and by induction $S_t(\tau)\ne\emptyset$. If $S_t\subseteq D$, closure of $D$ gives $S_T\subseteq D$,
hence $S_T\cap F=\emptyset$ and $V(S_T)=\textsf{violation}$. If $S_t\subseteq Z$, closure of $Z$ gives
$S_T\subseteq Z\subseteq F$ and $V(S_T)=\textsf{compliant}$. $\square$

**Lemma 1 (monotonicity).** Under Assumption S, for $\tau\le\tau'$:

1. $S_t(\tau)\subseteq S_t(\tau')$ for all $t$;
2. if $v(\tau')\ne\textsf{abstain}$ then $v(\tau)=v(\tau')$;
3. $\ell_{\rm ver}$, $\ell_{\rm miss}$ and $\ell_{\rm fa}$ are non-increasing and right-continuous in $\tau$,
   and all three vanish at $\tau=1$.

*Proof.* (1) $C_t(a;\tau)\subseteq C_t(a;\tau')$ by definition, so $L_t(\tau)\subseteq L_t(\tau')$, and
$\delta(\cdot,\cdot)$ is monotone in both arguments; induct on $t$. (2) By Lemma 0 the verdicts are
$V(S_T(\tau))$ and $V(S_T(\tau'))$. If $S_T(\tau')\subseteq F$ then $S_T(\tau)\subseteq F$. If
$S_T(\tau')\cap F=\emptyset$ then $S_T(\tau)\cap F=\emptyset$, and $S_T(\tau)\neq\emptyset$, so the
verdict is $\textsf{violation}$ and not vacuously $\textsf{compliant}$. (3) By (2), an error at
$\tau'$ is the same error at $\tau$, which gives monotonicity of each loss. The sets $C_t(a;\tau)$
change only at the finitely many values $\tau=c_t(a)$ and include the second value at equality, so
$\tau\mapsto S_T(\tau)$ is piecewise constant and right-continuous, and so are the losses. At $\tau=1$
the judged proposition has value set $\{0,1\}$, so $\sigma^*_t\in L_t(1)$ and $q^*_t\in S_t(1)$ for all
$t$; a definite verdict then agrees with $q^*_T$. $\square$

**Lemma 2 (hierarchy).** Under Assumption S, for every $\tau$,
$\ell_{\rm ver}(\tau)\le\ell_{\rm sr}(\tau)\le\ell_{\rm cov}(\tau)$, and the two coverage losses are
non-increasing, right-continuous and zero at $\tau=1$.

*Proof.* The second inequality holds because $\ell_{\rm sr}$ checks a subset of the pairs checked by
$\ell_{\rm cov}$. For the first, suppose $\ell_{\rm sr}(\tau)=0$; we show $q^*_t\in S_t(\tau)$ by
induction. Let $q^*_{t-1}\in S_{t-1}$. If $\sigma^*_t(a_t)\in C_t(a_t;\tau)$ (or nothing is judged),
then $\sigma^*_t\in L_t$ and $q^*_t\in S_t$. Otherwise $C_t(a_t;\tau)=\{1-\sigma^*_t(a_t)\}$, and since
$\ell_{\rm sr}(\tau)=0$ the proposition $a_t$ is not relevant at $q^*_{t-1}$. The flip $\sigma'$ of
$\sigma^*_t$ in $a_t$ lies in $\Sigma$ by Assumption S, hence in $L_t$, and
$\delta(q^*_{t-1},\sigma')=\delta(q^*_{t-1},\sigma^*_t)=q^*_t$ by irrelevance. So $q^*_T\in S_T(\tau)$,
and any definite verdict is correct: $\ell_{\rm ver}(\tau)=0$. Monotonicity and right-continuity
follow from the form of $C_t$ as in Lemma 1; at $\tau=1$ every value set contains the truth. $\square$

*Remark (free alphabets).* If $\Sigma=\{0,1\}^{AP}$ and several propositions are judged at one step,
Lemmas 1 and 2 hold without Assumption S: in Lemma 2, flip the uncovered irrelevant propositions one
at a time.

*Remark (relevance filtering).* Replacing $C_t(a;\tau)$ by $\{0,1\}$ for a proposition that is
irrelevant at every state of $S_{t-1}$ leaves $S_t$ unchanged, so the labeler need not be queried for
it. d'Amorim and Rosu (CAV 2005) already evaluate predicates by need per monitor state; with site
gating and early stopping this saves nothing measurable on our rules, and we do not claim it.

## 3. Risk control

**Units.** The exchangeable unit is the task. Task $i$ has a fixed, outcome-independent set $P_i$ of
(trajectory, rule) pairs and task loss $\bar\ell_i(\tau)=\frac1{|P_i|}\sum_{\pi\in P_i}\ell_\pi(\tau)$
for one of the losses above. By Lemmas 1 and 2, $\bar\ell_i$ takes values in $[0,1]$, is
non-increasing and right-continuous, and $\bar\ell_i(1)=0$. Steps within a trajectory are never
treated as exchangeable.

**Assumption A.** The calibration tasks $1,\dots,n$ and the test task $n+1$ are exchangeable.

**Theorem 1 (verdict-level risk control).** Let $\hat R_n(\tau)=\frac1n\sum_{i\le n}\bar\ell_i(\tau)$,
$\alpha\ge\frac1{n+1}$, and

$$\hat\tau=\inf\Big\{\tau\in[0,1]:\ \tfrac{n}{n+1}\hat R_n(\tau)+\tfrac1{n+1}\le\alpha\Big\}.$$

Under Assumptions S and A, $\ \mathbb E\big[\bar\ell_{n+1}(\hat\tau)\big]\le\alpha$.

*Proof.* This is Theorem 1 of Angelopoulos et al. (Conformal Risk Control, ICLR 2024) with loss bound
$1$; we repeat the argument. The set is non-empty since $\hat R_n(1)=0$ and $\alpha\ge\frac1{n+1}$. Let
$\hat R_{n+1}(\tau)=\frac1{n+1}\sum_{i\le n+1}\bar\ell_i(\tau)$ and
$\hat\tau'=\inf\{\tau:\hat R_{n+1}(\tau)\le\alpha\}$. Since $\bar\ell_{n+1}\le1$,
$\hat R_{n+1}(\tau)\le\frac n{n+1}\hat R_n(\tau)+\frac1{n+1}$, so $\hat\tau'\le\hat\tau$ and, by
monotonicity, $\bar\ell_{n+1}(\hat\tau)\le\bar\ell_{n+1}(\hat\tau')$. The threshold $\hat\tau'$ is a
symmetric function of the $n+1$ tasks, so by exchangeability
$\mathbb E[\bar\ell_{n+1}(\hat\tau')]=\mathbb E[\hat R_{n+1}(\hat\tau')]$, and
$\hat R_{n+1}(\hat\tau')\le\alpha$ by right-continuity. $\square$

With $\bar\ell=\bar\ell_{\rm ver}$ the statement reads: *the expected fraction of a test task's
(trajectory, rule) pairs on which the monitor commits to a wrong verdict is at most $\alpha$.*

**Corollary 1 (grid).** If $G\ni1$ is a finite grid and $\hat\tau_G$ is its smallest element satisfying
the condition of Theorem 1, then $\hat\tau_G\ge\hat\tau$ and $\mathbb E[\bar\ell_{n+1}(\hat\tau_G)]\le\alpha$.
Because the empirical risk is monotone, $\hat\tau_G$ can be found by bisection.

**Corollary 2 (coverage calibration is a conservative special case).** Calibrating with
$\bar\ell_{\rm sr}$ or $\bar\ell_{\rm cov}$ gives thresholds
$\hat\tau_{\rm cov}\ge\hat\tau_{\rm sr}\ge\hat\tau_{\rm ver}$ on the same calibration set, and each
also controls the verdict loss at level $\alpha$ (Lemma 2 and Theorem 1).

**Corollary 3 (per-rule thresholds).** The automata run in parallel without a product, so the loss of
rule $r$ depends only on its own threshold. Applying Theorem 1 separately to each rule with
$P_i^r=\{\text{pairs of task } i \text{ for rule } r\}$ gives $\mathbb E[\bar\ell^{\,r}_{n+1}(\hat\tau_r)]\le\alpha$
for every $r$, which implies the bound for the average over rules. A single threshold calibrated on
the rule average does not bound any individual rule (one of $K$ rules can run at up to $K\alpha$).

**Corollary 4 (two error budgets).** Let $\hat\tau_{\rm miss}$ and $\hat\tau_{\rm fa}$ be calibrated
with $\bar\ell_{\rm miss}$ at level $\alpha_{\rm m}$ and with $\bar\ell_{\rm fa}$ at level
$\alpha_{\rm f}$. At $\hat\tau=\max(\hat\tau_{\rm miss},\hat\tau_{\rm fa})$ both
$\mathbb E[\bar\ell_{\rm miss}]\le\alpha_{\rm m}$ and $\mathbb E[\bar\ell_{\rm fa}]\le\alpha_{\rm f}$ hold,
by monotonicity of each loss. These are joint rates, for example
$P(\text{true violation and declared compliant})$.

**Proposition 1 (class-conditional control).** Assume the tasks are i.i.d. Fix a class
$c\in\{\textsf{violation},\textsf{compliant}\}$, let $P_i^c\subseteq P_i$ be the pairs of task $i$ whose
true verdict is $c$, and $\bar\ell_i^{\,c}(\tau)$ the mean verdict loss over $P_i^c$, defined for tasks
with $P_i^c\ne\emptyset$. Let $n_c$ be the number of such calibration tasks and calibrate $\hat\tau_c$
on them as in Theorem 1 with $\alpha\ge\frac1{n_c+1}$. Then

$$\mathbb E\big[\bar\ell_{n+1}^{\,c}(\hat\tau_c)\ \big|\ P_{n+1}^c\ne\emptyset\big]\le\alpha .$$

For $c=\textsf{violation}$ this bounds the task-averaged miss rate among true violations.

*Proof.* Whether $P_i^c\ne\emptyset$ is a function of task $i$ alone. Conditionally on which tasks
satisfy it, those tasks are i.i.d. draws from the conditional task distribution, hence exchangeable,
and Theorem 1 applies to them. $\square$

The condition $\alpha\ge\frac1{n_c+1}$ is the binding constraint in practice: twelve calibration tasks
with a violation cannot certify a miss rate below $1/13\approx0.077$. Sparse rules can be pooled by
taking $P_i^c$ over several rules with one shared threshold; the guarantee is then for the pooled
average. Stratified budgets of this kind follow Role-Stratified CRC (arXiv 2607.24343) and are not
claimed as a contribution.

## 4. What the guarantee does not say

1. **Conditional error.** $P(\text{wrong}\mid\text{definite})\le\alpha/P(\text{definite})$ is all that
   follows; confident labeling errors do not trigger abstention and concentrate among the definite
   verdicts. Conformal selection (Jin and Candes, JMLR 2023) is the tool for a conditional guarantee.
2. **Triviality.** If the hard-label error is at most about $\alpha$, then $\hat\tau<1/2$ and the
   method is the hard-label monitor. If violations are rarer than $\alpha$, a monitor that always says
   compliant satisfies the joint bound. Hence Corollary 4 and Proposition 1.
3. **Intermediate flags.** The bound covers early violation, early permanent compliance and the
   end-of-trace verdict. It does not cover the running "possible violation" status, and a threshold
   chosen with the verdict loss does not keep $q^*_t$ inside $S_t$.
4. **Truth.** $\sigma^*$ is the human label (pilot: adjudicated; evaluation: reviewer-checked, with an independent
   second annotation as a sensitivity check). The guarantee is relative to it.
5. **Injected violations.** Natural and injected violations are not exchangeable. A bound calibrated
   on one does not transfer to the other.
6. **Escalation.** If abstentions are resolved by a human who returns the true verdict, the error of
   the combined system equals the joint error and inherits the bound. Intermediate automated
   escalation levels are not covered.
7. **Distribution.** The bound is marginal over the calibration draw and holds for the task and agent
   mixture the calibration tasks come from.
