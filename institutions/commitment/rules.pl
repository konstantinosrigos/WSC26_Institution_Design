:- multifile rule/4.
:- multifile institution_param/2.

% -------------------------------------------------------------------
% Central regime parameter block (consumed by Python simulation layer)
% -------------------------------------------------------------------
% Payoff/friction parameters
institution_param(compensation, 0.0).
institution_param(failed_coordination_penalty, 0.4).
institution_param(one_refusal_failure_penalty, 0.4).
institution_param(mismatch_failure_penalty, 1.1).

% Opportunity generation ranges
institution_param(status_quo_min, 8.0).
institution_param(status_quo_max, 12.0).
institution_param(giver_disutility_min, 0.7).
institution_param(giver_disutility_max, 1.5).
institution_param(surplus_if_a_executes_min, 3.6).
institution_param(surplus_if_a_executes_max, 5.4).
institution_param(surplus_if_b_executes_min, 2.6).
institution_param(surplus_if_b_executes_max, 4.4).
institution_param(can_take_probability, 0.85).
institution_param(executor_share_min, 0.68).
institution_param(executor_share_max, 0.78).

/*** IAD: Boundary rules ***/
rule(commitment, boundary, 0,
    if agent(Ag)
    then participates(Ag)
    where []).

/*** IAD: Position rules ***/
rule(commitment, position, 0,
    if participates(Ag)
    then role(Ag, carrier)
    where []).

rule(commitment, position, 0,
    if participates(Ag)
    then role(Ag, trip_owner)
    where []).

rule(commitment, position, 0,
    if participates(Ag)
    then role(Ag, potential_taker)
    where []).

rule(commitment, position, 0,
    if participates(Ag)
    then role(Ag, potential_giver)
    where []).

/*** IAD: Choice rules ***/
rule(commitment, choice, 0,
    if role(Ag, carrier)
    then can(Ag, take_other)
    where []).

rule(commitment, choice, 0,
    if role(Ag, carrier)
    then can(Ag, give_own)
    where []).

rule(commitment, choice, 0,
    if role(Ag, carrier)
    then can(Ag, refuse)
    where []).

/*** IAD: Aggregation rules ***/
rule(commitment, control, 0,
    if does(a, take_other) and does(b, give_own)
    then [ outcome(a_executes_both)
           and executes(a, ta)
           and executes(a, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, give_own) and does(b, take_other)
    then [ outcome(b_executes_both)
           and executes(b, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).

% Commitment mechanism: if both claim, institution mediates a winner.
rule(commitment, control, 0,
    if does(a, take_other) and does(b, take_other)
    then [ outcome(a_executes_both)
           and executes(a, ta)
           and executes(a, tb)
           withProb 0.5
         , outcome(b_executes_both)
           and executes(b, ta)
           and executes(b, tb)
           withProb 0.5 ]
    where []).

% Commitment mechanism: a unilateral taker can still be matched institutionally.
rule(commitment, control, 0,
    if does(a, take_other) and does(b, refuse)
    then [ outcome(a_executes_both)
           and executes(a, ta)
           and executes(a, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, refuse) and does(b, take_other)
    then [ outcome(b_executes_both)
           and executes(b, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, refuse) and does(b, refuse)
    then [ outcome(no_exchange)
           and executes(a, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, give_own) and does(b, give_own)
    then [ outcome(no_exchange)
           and executes(a, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, give_own) and does(b, refuse)
    then [ outcome(no_exchange)
           and executes(a, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).

rule(commitment, control, 0,
    if does(a, refuse) and does(b, give_own)
    then [ outcome(no_exchange)
           and executes(a, ta)
           and executes(b, tb)
           withProb 1.0 ]
    where []).
