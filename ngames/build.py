r"""Build a complete Extensive Form Game from an action situation description.

This script includes all the functions to create a complete Extensive Form
Game from a Prolog description using the syntax of if-then-where rules.

"""

import os
import networkx as nx
from copy import deepcopy
from pathlib import Path
from typing import List, Tuple, Dict
from pyswip import Prolog
from ngames.extensivegames import ExtensiveFormGame


def _split_top_level_args(args_str: str) -> List[str]:
    """Split a Prolog argument string at top-level commas."""
    args = []
    chunk = []
    depth = 0
    in_single_quote = False
    in_double_quote = False

    for ch in args_str:
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif not in_single_quote and not in_double_quote:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                args.append(''.join(chunk).strip())
                chunk = []
                continue
        chunk.append(ch)

    if chunk:
        args.append(''.join(chunk).strip())

    return args


def _term_text(term) -> str:
    """Return a Prolog term as text, compatible with old and new PySwip."""
    if isinstance(term, str):
        return term.strip().rstrip('.')

    value = getattr(term, "value", None)
    if value is not None:
        return str(value).strip().rstrip('.')

    return str(term).strip().rstrip('.')


def _term_args(term) -> List[str]:
    """Extract arguments from a Prolog compound term."""
    if hasattr(term, "args"):
        args = []
        for arg in term.args:
            if hasattr(arg, "value"):
                args.append(str(arg.value))
            else:
                args.append(str(arg))
        return args

    term_str = _term_text(term)
    left = term_str.find("(")
    right = term_str.rfind(")")
    if left < 0 or right < 0 or right <= left:
        return []
    return _split_top_level_args(term_str[left + 1:right])


def _term_arg(term, index: int) -> str:
    """Get a single argument from a Prolog term by index."""
    args = _term_args(term)
    if index >= len(args):
        raise ValueError("Term '{}' does not have argument #{}".format(
            _term_text(term), index))
    return args[index]


def build_game_round(identifier: str, threshold: int,
                     root_state_facts: List[str], expand_node: int,
                     node_counter: int, player_order: List[str],
                     prolog: Prolog) \
        -> Tuple[ExtensiveFormGame, Dict[int, bool], int]:
    r"""Build a round of the game (i.e. all possible state transitions).

    Build a round of the game, i.e. a restricted form of an extensive-form
    game, that models all the ways by which a pre-transition state might evolve
    given the joint actions that agents perform.

    Parameters
    ----------
    identifier : str
        Identifier for the action situation rules that we want to
        include when building the game.
    threshold : int
        The rules with priority over this threshold are not considered.
    root_state_facts : List[str]
        The fluents that hold true at the single pre-transition state.
    expand_node : int
        The integer for the node that is being expanded, that is the root of
        the game round.
    node_counter : int
        To ensure that node numbering in the game round does not clash with
        that of the general game.
    player_order : List[str]
        An order of the players to always add player's information sets in the
        same order.

    Returns
    -------
    ngames.evaluation.ExtensiveFormGame
        The game round.
    Dict[int, bool]
        A dictionary mapping the terminal nodes of the game tree to whether the
        termination conditions are met at them.
    int
        The updated node counter.

    """
    game_round = ExtensiveFormGame(ID=identifier)
    game_round.add_node(expand_node, is_root=True)
    game_round.state_fluents = {}
    node_counter += 1

    # get the available actions
    q = prolog.query("get_simple_consequences({},choice,{},L)".format(
        identifier, threshold))
    q_list = list(q)
    q.close()
    assert len(q_list) == 1, "Prolog found {} action lists, not 1" \
        .format(len(q_list))
    sln = q_list[0]['L']
    actions = {}
    for x in sln:
        participant = _term_arg(x, 0)
        action = _term_arg(x, 1)
        try:
            actions[participant].append(action)
        except KeyError:
            actions[participant] = [action]
    game_round.add_players(*actions.keys())

    # build the game tree skeleton in a breadth-first manner
    w = {game_round.game_tree.root}
    w_prime = set()
    for player in player_order:
        try:
            player_actions = actions[player]
        except KeyError:
            continue
        for x in w:
            game_round.set_node_player(x, player)
            for a in player_actions:
                game_round.add_node(node_counter)
                w_prime.add(node_counter)
                game_round.add_edge(x, node_counter, a)
                node_counter += 1
        game_round.add_information_sets(player, w)
        w = deepcopy(w_prime)
        w_prime = set()

    # process the terminal nodes
    tau = {}
    initial_terminal_nodes = deepcopy(game_round.game_tree.terminal_nodes)
    for z in initial_terminal_nodes:
        path = nx.bidirectional_shortest_path(game_round.game_tree,
                                              game_round.game_tree.root, z)

        for i in range(len(path[:-1])):
            who = game_round.turn_function[path[i]]
            what = game_round.game_tree.get_edge_data(path[i], path[i + 1])
            prolog.assertz("does({},{})".format(who, what['action']))

        q = prolog.query("terminal")
        list_q = list(q)
        q.close()
        is_terminal = bool(len(list_q))

        q = prolog.query("get_control_consequences({},{},[{}],S,P)".format(
            identifier, threshold, ','.join(root_state_facts)))
        q_list = list(q)
        q.close()
        assert len(q_list) == 1, "Prolog found {} next states sets, not 1" \
            .format(len(q_list))
        probs = q_list[0]['P']
        S_t1 = []
        for functors_state in q_list[0]['S']:
            state = []
            for functor in functors_state:
                state.append(_term_text(functor))
            S_t1.append(state)

        if len(S_t1) == 1:
            tau[z] = is_terminal
            game_round.state_fluents[z] = S_t1[0]

        else:
            game_round.set_node_player(z, 'chance')
            probability_distribution = {}
            for s, p in zip(S_t1, probs):
                game_round.add_node(node_counter)
                game_round.add_edge(z, node_counter, label='')
                probability_distribution[(z, node_counter)] = p
                s.sort()
                game_round.state_fluents[node_counter] = s
                tau[node_counter] = is_terminal
                node_counter += 1
            game_round.set_probability_distribution(z,
                                                    probability_distribution)

        prolog.retractall("does(_,_)")

    return game_round, tau, node_counter


def build_full_game(folder: str, identifier: str,
                    threshold: int = 1000,
                    max_rounds: int = 10) \
        -> ExtensiveFormGame:
    r"""Build a complete game tree from an action situation Prolog description.

    This function takes in a complete Prolog description of an action situation
    according to the if-then-where rules and builds the complete Extensive Form
    Game that models the situation. It expands the game tree in a breadth-first
    fashion.

    Additional attributes of the game not included in the original
    implementation are added to the returned game:
    * roles: a dictionary mapping the participants to the list of roles they 
    assume.
    * node_rounds: a dictionary mapping every non-intermediate node to
    the number of rounds performed to get there.
    * state_fluents: a dictionary mapping every non-intermediate node to
    the predicates that hold true in that node.

    
    Parameters
    ----------
    folder : str
        Folder where the agents.pl, states.pl and rules.pl files are placed.
    identifier : str
        Identifier for the action situation rules that we want to
        include when building the game.
    threshold : int, optional
        if-then-where rules, of any type, whose priority exceeds the threshold
        are not considered while building the game. Default is 1000.
    max_rounds : int, optional
        The maximum number of rounds to perform during the game tree expansion.
        The default is 10.

    Returns
    -------
    ngames.evaluation.ExtensiveFormGame
        The resulting Extensive Form Game corresponding to the action
        situation.

    """
    prolog = Prolog()
    script_path = str(Path(__file__).parent.absolute()).replace('\\', '/')
    prolog.consult("{}/interpreter.pl".format(script_path))
    prolog.consult("{}/agents.pl".format(folder))
    prolog.consult("{}/rules.pl".format(folder))
    prolog.consult("{}/states.pl".format(folder))

    game = ExtensiveFormGame(ID=identifier)

    # STEP 1: Get the participants and add them to the game
    q = prolog.query("get_simple_consequences({},boundary,{},L)".format(
        identifier, threshold))
    q_list = list(q)
    q.close()
    assert len(q_list) == 1, "Prolog found {} participant lists, not 1" \
        .format(len(q_list))
    phi = q_list[0]['L']
    for p in phi:
        game.add_players(_term_arg(p, 0))
        prolog.assertz(_term_text(p))
    players = game.players

    # STEP 2: Assign the participants to roles
    q = prolog.query("get_simple_consequences({},position,{},L)".format(
        identifier, threshold))
    q_list = list(q)
    q.close()
    assert len(q_list) == 1, "Prolog found {} roles lists, not 1" \
        .format(len(q_list))
    rho = q_list[0]['L']
    game.roles = {p: [] for p in game.players}
    for r in rho:
        player = _term_arg(r, 0)
        role = _term_arg(r, 1)
        try:
            game.roles[player].append(role)
        except KeyError:
            game.roles[player] = [role]
        prolog.assertz(_term_text(r))

    # STEP 3: Get initial state and add it as root node to game
    q = prolog.query("initially(F)")
    initial_facts = []
    for sln in q:
        initial_facts.append(sln['F'])
    q.close()
    initial_facts.sort()
    node_counter = 1
    game.add_node(node_counter, is_root=True)
    game.state_fluents = {node_counter: initial_facts}
    game.node_rounds = {node_counter: 0}
    expand_queue = [node_counter]
    node_counter += 1

    # MAIN LOOP
    while expand_queue:
        # Get the node to be expanded and assert into the database
        expand_node = expand_queue.pop(0)
        expand_node_facts = game.state_fluents[expand_node]
        for f in expand_node_facts:
            prolog.assertz(f)

        # Number of rounds exceeds maximum
        if game.node_rounds[expand_node] >= max_rounds:
            for f in expand_node_facts:
                prolog.retractall(f)
            continue

        # Check if the current node is terminal
        q = prolog.query("terminal")
        list_q = list(q)
        q.close()
        is_terminal = bool(len(list_q))
        if is_terminal:
            for f in expand_node_facts:
                prolog.retractall(f)
            continue

        game_round, tau, node_counter_updated = \
            build_game_round(identifier,
                             threshold,
                             expand_node_facts,
                             expand_node,
                             node_counter - 1,
                             players,
                             prolog)
        node_counter = node_counter_updated

        for f in expand_node_facts:
            prolog.retract(f)

        # append game round to the main game tree
        game.game_tree = \
            nx.algorithms.operators.binary.compose(game.game_tree,
                                                   game_round.game_tree)
        game.game_tree.root = 1
        game.turn_function.update(game_round.turn_function)
        game.game_tree.terminal_nodes = [n for n in game.game_tree.nodes
                                         if n not in game.turn_function.keys()]

        # information sets
        for p in game.players:
            try:
                game.add_information_sets(
                    p, game_round.information_partition[p][0])
            except KeyError:
                pass

        # probability distribution
        game.probability.update(game_round.probability)

        # state fluents
        game.state_fluents.update(game_round.state_fluents)

        # update queue and node rounds
        for z in game_round.game_tree.terminal_nodes:
            game.node_rounds[z] = game.node_rounds[expand_node] + 1
            if tau[z] is False:
                expand_queue.append(z)

    prolog.retractall("role(_,_)")
    prolog.retractall("participates(_)")

    return game


def build_game_from_rule_combination(folder: str, identifier: str,
                                     rule_combination: Dict[str, int],
                                     **kwargs) -> ExtensiveFormGame:
    r"""Build a full game from the combination of rules in place.

    Beyond the default rules (which are always necessary), the additional rules
    in place are represented by: (1) a selection of all the possible additional
    rules that wish to be implemented; (2) an ordering over the selected
    additional rules to establish their priorities. This function build the
    extensive-form game from such a representation of the rules in place.

    Parameters
    ----------
    folder : str
        The folder where the databases are.
    identifier : str
        A unique identifier for the action situation being modelled.
    rule_combination : Dict[str,int]
        A dictionary mapping the priorities of additional rules to an integer.
        Rules assigned a priority of -1 are considered inactive. For the active
        rules, they should all be assigned different strictly positive
        integers.
    **kwargs
        Additional keyword argument to be passed to ``build_full_game``, namely
        ``threshold`` and ``max_rounds``.

    Returns
    -------
    ExtensiveFormGame
        The resulting Extensive Form Game corresponding to the action situation
        with that combination of rules in place.

    """
    databases = ['agents', 'states', 'rules']

    for db in databases:
        input_file = open(folder + '/' + db + 'DB.pl', 'rt')
        output_file = open(folder + '/' + db + '.pl', 'wt')

        for line in input_file:
            for p_variable, p_value in rule_combination.items():
                line = line.replace(p_variable, str(p_value))
            output_file.write(line)

        input_file.close()
        output_file.close()

    game = build_full_game(folder, identifier, **kwargs)

    for db in databases:
        os.remove(folder + '/' + db + '.pl')

    return game


if __name__ == '__main__':
    pass
