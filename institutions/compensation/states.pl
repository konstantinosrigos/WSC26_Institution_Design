:- multifile terminal/0.
:- multifile incompatible/2.

:- dynamic outcome/1.
:- dynamic executes/2.
:- dynamic transfer/3.

terminal :- outcome(_).

incompatible(outcome(_), L) :-
    member(outcome(_), L).

incompatible(executes(_, Trip), L) :-
    member(executes(_, Trip), L).
