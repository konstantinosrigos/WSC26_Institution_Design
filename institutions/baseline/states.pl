:- multifile terminal/0.
:- multifile incompatible/2.

:- dynamic outcome/1.
:- dynamic executes/2.
:- dynamic transfer/3.

% Action situation ends once an institutional outcome has been produced.
terminal :- outcome(_).

% Scope/incompatibility conditions for valid post-action states.
incompatible(outcome(_), L) :-
    member(outcome(_), L).

incompatible(executes(_, Trip), L) :-
    member(executes(_, Trip), L).
