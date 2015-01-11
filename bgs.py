__author__ = 'Walter Da Col <walter.dacol@gmail.com>'
__license__ = """
The MIT License (MIT)

Copyright (c) 2015 Walter Da Col <walter.dacol@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE."""

import argparse
import urllib
import time
import pickle
import os.path
import logging
import math
import operator
import sys

# CONST
COLLECTION_URL = 'http://www.boardgamegeek.com/xmlapi/collection/%s'
BOARDGAME_URL = 'http://www.boardgamegeek.com/xmlapi/boardgame/%s?stats=1'
ALREADY_DOWNLOADED_PLAYERS = {}
REQUEST_DELAY = 2
MIN_VOTES_FOR_SUGGESTION = 10
MIN_VOTES_FOR_RATING = 100

# GENERAL FUNCTIONS


def load_object(filename):
    """
    Read an object from file using pickle

    :param filename: a filename
    :return: an object or None on errors
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'rb') as input:
                obj = pickle.load(input)
                return obj
        else:
            return None
    except:
        log().exception('Cannot read object from file')
        return None


def save_object(obj, filename):
    """
    Save an object to given filename using pickle

    :param obj: the object
    :param filename: a filename
    :return: True if no error, False otherwise
    """
    try:
        with open(filename, 'wb') as output:
            pickle.dump(obj, output, pickle.HIGHEST_PROTOCOL)
        return True
    except:
        log().exception('Cannot save object to file')
        return False


def standardize(value):
    """
    This method return a standardized float (round to 4 digits) and force value into 0.0 .. 1.0 range

    :param value: a Float value
    :return: a standardized float
    """
    return max(0.0, min(1.0, round(value, 4)))

# CLASSES


class GameStats():
    """
    Used to store player game statistics
    """
    owned = False
    rating = None
    play_count = 0
    want_to_play = False

    def __init__(self, game_id):
        self.game_id = game_id


class Player():
    """
    Player class
    """
    games_stats = {}
    is_guest = False

    def __init__(self, username, is_guest=False):
        self.username = username
        self.is_guest = is_guest

    @classmethod
    def load_from_cache(cls, username):
        """
        Load a player from cache

        :param username Which player load from disk
        :return: None if player is not cached, Player instance otherwise
        """
        obj = load_object(username + '.player')

        if obj is None:
            return None

        if isinstance(obj, Player):
            return obj
        else:
            log().warning('Invalid file for username %s' % username)
            return None

    @classmethod
    def create_players_group(cls, username_list, use_cache=True):
        group = []
        for username in username_list:
            p = None

            # Load from cache
            if use_cache:
                p = Player.load_from_cache(username)

            # If not in cache or clear cache directive
            if p is None:
                p = Player(username)

                # Load stats from BGG
                if p.download_player_stats():
                    p.save_to_cache()
                else:
                    log().error('Cannot load player data for %s, quit' % username)
                    exit(1)
            else:
                log().info('Loaded %s from cache' % username)

            if p:
                group.append(p)

        return group

    def download_player_stats(self):
        """
        Download player stats from BGG

        :return: True if everything is fine, False otherwise
        """
        def get_xml(username):
            url = COLLECTION_URL % urllib.parse.quote_plus(username)
            r = requests.get(url, timeout=5)

            log().debug('Request url: %s' % r.url)

            if r.status_code == requests.codes.ok:
                return r.text

            if r.status_code != requests.codes.accepted:
                log().error('Cannot retrieve xml')
                return None
            else:
                log().debug('Got accepted code, retrying after %d second..' % REQUEST_DELAY)
                time.sleep(REQUEST_DELAY)
                return get_xml(username)

        def get_games_from_xml(xml):
            try:
                soup = BeautifulSoup(xml, 'xml')
                games = {}

                if soup.errors:
                    log().error('Cannot fetch player data')
                    for error in soup.errors.find_all('error'):
                        log().error('\t%s' % error.message.string)
                    return None

                for game in soup.find_all('item'):

                    if not game.has_attr('objectid'):
                        log().warning('Missing objectid')
                        continue

                    game_id = int(game['objectid'])
                    game_stat = GameStats(game_id)

                    # Play count
                    if game.numplays is None:
                        log().warning('Missing numplays for game with id %d' % game_id)
                        continue

                    game_stat.play_count = int(game.numplays.string)

                    if game.status is None:
                        log().warning('Missing status for game with id %d' % game_id)
                        continue

                    # Owned
                    if (game.status.has_attr('own')) & (game.status['own'] == u'1'):
                        game_stat.owned = True

                    # Want to play
                    if (game.status.has_attr('wanttoplay')) & (game.status['wanttoplay'] == u'1'):
                        game_stat.want_to_play = True

                    # Rating
                    game_rating = game.stats.rating.get('value', 'N/A')
                    if game_rating != 'N/A':
                        game_stat.rating = float(game_rating) / 10.0

                    games[game_id] = game_stat

                return games
            except:
                log().exception("Parsing errors")
                return None

        if self.username in ALREADY_DOWNLOADED_PLAYERS:
            self.games_stats = ALREADY_DOWNLOADED_PLAYERS[self.username]
            log().debug('Player data already downloaded, skip')
            return True

        log().info('Dowloading data for player %s ..' % self.username)
        log().debug('Requesting xml..')
        player_xml = get_xml(self.username)

        if player_xml:
            log().debug('Parsing xml ..')
            parsed_games = get_games_from_xml(player_xml)

            if parsed_games is None:
                return False

            self.games_stats = parsed_games

            ALREADY_DOWNLOADED_PLAYERS[self.username] = parsed_games

            log().debug('Download Ok')
            return True
        else:
            log().error('Cannot fetch player data')
            return False

    def save_to_cache(self):
        """
        Save player data to cache

        :return: True if everything is fine, False otherwise
        """
        return save_object(self, self.username + '.player')


class Game():
    """
    Used to store game information
    """
    game_id = None
    name = None
    player_min = None
    player_max = None
    playing_time = None
    suggested_players = None
    is_an_expansion = False
    expansion_of = None
    average_weight = None
    average_rating = None

    def __init__(self, game_id):
        self.game_id = game_id

    @classmethod
    def load_games_collection_from_cache(cls, name):
        """
        Load a list of Games from cache

        :param name Collection name
        :return: None on error, a list of Game object otherwise
        """

        obj = load_object('%s.collection' % name)
        if obj:
            if isinstance(obj, dict):
                for key in obj:
                    if not isinstance(obj[key], Game):
                        log().warning('Invalid file for collection %s' % name)
                        return None
                return obj
            else:
                log().warning('Invalid file for collection %s' % name)
                return None
        return None

    @classmethod
    def download_games_data(cls, game_id_list):
        def get_xml(game_id_list, retry_count=0):
            ids = ','.join([str(game_id) for game_id in game_id_list])
            url = BOARDGAME_URL % ids
            r = requests.get(url, timeout=30)

            log().debug('Requesting games xml using %s ..' % r.url)

            if r.status_code == requests.codes.ok:
                return r.text

            if r.status_code != requests.codes.accepted:
                log().error('Cannot retrieve games xml')
                log().debug(r.text)
                return None
            else:
                if retry_count < 10:
                    log.debug('Retry #%d' % retry_count)
                    time.sleep(2)
                    return get_xml(game_id_list, retry_count + 1)
                else:
                    log().error('Cannot retrieve games xml')
                    log().debug(r.text)
                    return None

        def get_games_from_xml(xml):
            soup = BeautifulSoup(xml)
            games = {}

            for game in soup.find_all('boardgame'):
                if not game.has_attr('objectid'):
                    log.warning('A game does not have and id')
                    continue

                game_id = int(game['objectid'])
                g = Game(game_id)

                names = game.find_all('name')
                name = [name.text for name in names if (name.get('primary', 'false') == 'true')]
                if not name:
                    log().warning('A game [%d] does not have and name' % game_id)
                    continue

                g.name = name[0]

                # Players
                if (game.minplayers is not None) & (int(game.minplayers.string) > 0):
                    g.player_min = int(game.minplayers.string)

                if (game.maxplayers is not None) & (int(game.maxplayers.string) > 0):
                    g.player_max = int(game.maxplayers.string)

                if (game.minplayers is not None) & (int(game.playingtime.string) > 0):
                    g.playing_time = int(game.playingtime.string)

                # Expansions
                expansion_of = []
                expansions = game.find_all('boardgameexpansion')
                for expansion in expansions:
                    if expansion.get('inbound', 'false') == 'true':
                        expansion_of_id = int(expansion.get('objectid', None))
                        if expansion_of_id is not None:
                            expansion_of.append(expansion_of_id)

                if expansion_of:
                    g.is_an_expansion = True
                    g.expansion_of = set(expansion_of)

                # Suggestions
                polls = game.find_all('poll', {'name': 'suggested_numplayers'})
                if (len(polls) > 0) & (g.player_max is not None):
                    poll = polls[0]
                    suggested_players = {}

                    results = poll.find_all('results')
                    for result in results:
                        if result.has_attr('numplayers'):
                            player_num_string = result['numplayers']
                            player_nums = []
                            if '+' in player_num_string:
                                more_than = 0
                                try:
                                    more_than = int(player_num_string.strip('+'))
                                except:
                                    log().exception('Cannot convert numplayers string to int')
                                    continue

                                if g.player_max < (more_than + 1):
                                    continue

                                player_nums = range(more_than + 1, g.player_max + 1)
                            else:
                                try:
                                    player_nums = [int(player_num_string)]
                                except:
                                    log().exception('Cannot convert numplayers string to int')
                                    continue

                            for option in result.find_all('result'):
                                if (not option.has_attr('value')) | (not option.has_attr('numvotes')):
                                    continue

                                value = option['value']
                                votes = 0
                                try:
                                    votes = int(option['numvotes'])
                                except:
                                    log().exception('Cannot convert numvotes string to int')
                                    continue

                                for pn in player_nums:
                                    if pn not in suggested_players:
                                        suggested_players[pn] = {}
                                    suggested_players[pn][value] = suggested_players[pn].get(value, 0) + votes
                        else:
                            continue

                    if suggested_players:
                        g.suggested_players = suggested_players.copy()
                        # Clean suggestion with few votes
                        for pn in suggested_players:
                            all_votes = sum(suggested_players[pn].values())
                            if all_votes < MIN_VOTES_FOR_SUGGESTION:
                                g.suggested_players.pop(pn)
                        if g.suggested_players == {}:
                            g.suggested_players = None

                if game.statistics and game.statistics.ratings:
                    # Weight
                    if game.statistics.ratings.averageweight:
                        g.average_weight = float(game.statistics.ratings.averageweight.string)

                    # Rating
                    if game.statistics.ratings.usersrated and game.statistics.ratings.average:
                        try:
                            number_of_votes = int(game.statistics.ratings.usersrated.string)
                            if number_of_votes >= MIN_VOTES_FOR_RATING:
                                g.average_rating = float(game.statistics.ratings.average.string) / 10.0
                        except:
                            log().exception('Cannot retrive game rating')

                games[game_id] = g

            return games

        xml = get_xml(game_id_list)
        if xml:
            return get_games_from_xml(xml)
        else:
            return None

    def __repr__(self):
        return '<Game object with id %s and name %s>' % (str(self.game_id), str(self.name))

    def __str__(self):
        return '<Game object with id %s and name %s>' % (str(self.game_id), str(self.name))


class Master():
    """
    The Master class :P (do all the works)
    """
    __game_group = []
    __clear_cache = False
    __collection_group = []
    __collection = {}
    __available_collection = set([])
    __possible_collection = set([])
    __evaluations = {}
    __detailed_evaluations = {}

    def __init__(self, clear_cache=False):
        self.__clear_cache = clear_cache

    def add_known_players(self, username_list):
        """
        This method adds BBG users to game group

        :param username_list: a list of BGG usernames
        """
        log().info('Adding BGG players ..')
        self.__game_group = Player.create_players_group(username_list, use_cache=(not self.__clear_cache))

    def add_guests(self, number_of_guests):
        """
        This method adds guests (not BGG users) to game group

        :param number_of_guests: how many guests in game group
        """
        log().info('Adding guests ..')
        for i in range(0, number_of_guests):
            self.__game_group.append(Player('GUEST_%d' % i, is_guest=True))

    def use_games_owned_by_these_players(self, username_list):
        """
        This method gather all games owned by a list of BGG users

        :param username_list: a list of BGG usernames
        """
        log().info('Adding player game collections ..')
        self.__collection_group = Player.create_players_group(username_list, use_cache=(not self.__clear_cache))

        # Select only owned games
        collection_group_games = set([])
        for player in self.__collection_group:
            for game_id in player.games_stats:
                if player.games_stats[game_id].owned:
                    collection_group_games.add(game_id)

        # Which games must be downloaded
        missing_games = collection_group_games

        if not self.__clear_cache:
            log().info('Loading games data from cache ..')
            cached_collection = Game.load_games_collection_from_cache('master')
            if cached_collection:
                self.__collection.update(cached_collection)
                # Remove cached games from missing games
                missing_games.difference_update(cached_collection.keys())

        if missing_games:
            log().info('Downloading games data from BGG ..')
            self.__collection.update(Game.download_games_data(missing_games))

        # Check if we have at least one game
        if self.__collection:
            log().debug('Saving collection ..')
            save_object(self.__collection, 'master.collection')
        else:
            log().error('Cannot find games in given collections, exit')
            exit()

    def rate_our_games(self, playing_time=None, weight=None):
        """
        This method rate every playable games

        :param playing_time: desired playing time (or None)
        :param weight: desired game weight (or None)
        """
        # Select only owned games (cache can contain games owned by other people)
        for game_id in self.__collection:
            if any([player.games_stats[game_id].owned for player in self.__collection_group if (game_id in player.games_stats)]):
                self.__available_collection.add(game_id)

        if not self.__available_collection:
            log().error('No available games, check usernames and/or collections for owned games')
            exit()

        # Select only playable games
        number_of_players = len(self.__game_group)
        for game_id in self.__available_collection:
            g = self.__collection[game_id]

            # Check number of players
            if (g.player_min is not None) & (g.player_max is not None):
                if number_of_players not in range(g.player_min, g.player_max + 1):
                    continue

            # Check if we own base game of expansions
            if g.is_an_expansion:
                if all([(base_id not in self.__available_collection) for base_id in g.expansion_of]):
                    continue

            self.__possible_collection.add(game_id)

        # If no game is possible
        if not self.__possible_collection:
            log().error('No possible games for this game group, sorry')
            exit()

        # Begin rating calculation
        score_weights = {
            'score_playing_time': 0.4,
            'score_weight': 0.4,
            'suggested_values': 0.2,
            'players_score': 0.4,
        }
        scores = {}
        for game_id in self.__possible_collection:
            g = self.__collection[game_id]
            self.__detailed_evaluations[game_id] = {}

            # GENERAL

            # Playing time
            scores['score_playing_time'] = [0.0, 0.0]
            if weight:
                scores['score_playing_time'] = [0.5, score_weights['score_playing_time']]
                self.__detailed_evaluations[game_id]['score_playing_time'] = ['Default', score_weights['score_playing_time']]

            if (g.playing_time is not None) & (playing_time is not None):
                delta_time = abs(playing_time - g.playing_time)
                max_delta = playing_time  # (-T < t < 2T )
                if delta_time >= max_delta:
                    scores['score_playing_time'] = [0.0, score_weights['score_playing_time']]
                else:
                    raw_score = delta_time * (3.0 / max_delta) + 2.0
                    scores['score_playing_time'] = [1.0 - (pow(2, raw_score) - 4.0) / 28.0, score_weights['score_playing_time']]
                self.__detailed_evaluations[game_id]['score_playing_time'] = scores['score_playing_time']

            # Weight
            scores['score_weight'] = [0.0, 0.0]
            if weight:
                scores['score_weight'] = [0.5, score_weights['score_weight']]
                self.__detailed_evaluations[game_id]['score_weight'] = ['Default', score_weights['score_weight']]

            if (g.average_weight is not None) & (weight is not None):
                delta_weight = abs(weight - g.average_weight)
                max_delta = 2.5
                if delta_weight >= max_delta:
                    scores['score_weight'] = [0.0, score_weights['score_weight']]
                else:
                    raw_score = delta_weight * (2.0 / max_delta) + 2.0
                    scores['score_weight'] = [1.0 - (pow(2, raw_score) - 4.0) / 16.0, score_weights['score_weight']]
                self.__detailed_evaluations[game_id]['score_weight'] = scores['score_weight']

            # BGG user suggested number of player
            scores['suggested_values'] = [0.6, score_weights['suggested_values']]
            self.__detailed_evaluations[game_id]['suggested_values'] = ['Default', score_weights['suggested_values']]
            if g.suggested_players:
                suggested_values = g.suggested_players.get(number_of_players, None)
                if suggested_values:
                    suggested_max_score = sum(suggested_values.values())
                    score_suggestion = suggested_values['Not Recommended'] * 0.5 / suggested_max_score
                    score_suggestion += suggested_values['Best'] * 1.0 / suggested_max_score
                    score_suggestion += suggested_values['Recommended'] * 0.5 / suggested_max_score
                    score_suggestion -= suggested_values['Not Recommended'] * 0.5 / suggested_max_score
                    scores['suggested_values'] = [max(0.0, score_suggestion), score_weights['suggested_values']]
                    self.__detailed_evaluations[game_id]['suggested_values'] = scores['suggested_values']

            # PERSONAL

            # Players score (use average rating + play count + want + user rating)
            scores['players_score'] = [0.5, score_weights['players_score']]
            players_score = 0.0
            divide_by = 0.0
            if g.average_rating:
                # This rating is less important compared to game group ratings
                players_score = g.average_rating * 0.5
                divide_by = 0.5

            for player in self.__game_group:
                if player.is_guest:
                    continue

                if game_id not in player.games_stats:
                    continue

                stats = player.games_stats[game_id]

                partial = players_score  #Hack
                if stats.want_to_play:
                    if stats.rating:
                        players_score += 0.8
                        players_score += stats.rating * 0.2
                    else:
                        players_score += 0.9
                else:
                    if stats.rating:
                        if stats.play_count != 0:
                            players_score += math.exp(stats.play_count / pow(2.0, stats.rating * 10) * -1.0) * stats.rating
                        else:
                            players_score += stats.rating * 0.8
                    else:
                        continue

                divide_by += 1.0

                if 'players_score' not in self.__detailed_evaluations[game_id]:
                    self.__detailed_evaluations[game_id]['players_score'] = {}
                self.__detailed_evaluations[game_id]['players_score'][player.username] = standardize(players_score - partial)

            if divide_by > 0.0:
                scores['players_score'] = [players_score / divide_by, score_weights['players_score']]
                self.__detailed_evaluations[game_id]['all_players_score'] = scores['players_score']

            # The .-=[ ** SCORE ** ]=-.
            score_weights_sum = sum([score[1] for score in scores.values()])
            if score_weights_sum > 0.0:
                final_score = sum([score[0] * score[1] for score in scores.values()]) / score_weights_sum
                self.__evaluations[game_id] = standardize(final_score)
            else:
                self.__evaluations[game_id] = 0.0

    def show_your_decision(self, limit, separate_exp=False):
        def build_exp_graph():
            g = networkx.DiGraph()
            for game_id in self.__possible_collection:
                game = self.__collection[game_id]
                if game.expansion_of:
                    g.add_node(game_id, pMin=game.player_min, pMax=game.player_max, isBase=(not game.is_an_expansion))
                    for base_id in game.expansion_of:
                        if base_id in self.__available_collection:
                            base = self.__collection[base_id]
                            g.add_node(base_id, pMin=base.player_min, pMax=base.player_max, isBase=(not base.is_an_expansion))
                            g.add_edge(base_id, game_id)

            base_to_exp = {}
            for node, node_data in g.node.items():
                if not node_data['isBase']:
                    continue

                base_to_exp[node] = []
                for child, child_data in g.node.items():
                    if child_data['isBase']:
                        continue
                    if networkx.has_path(g, node, child):
                        for path in list(networkx.all_simple_paths(g, node, child)):
                            p_max = max([self.__collection[n].player_max for n in path if self.__collection[n].player_max is not None])
                            p_min = max([self.__collection[n].player_min for n in path if self.__collection[n].player_min is not None])
                            if p_max and p_min:
                                if len(self.__game_group) in range(p_min, p_max + 1):
                                    base_to_exp[node].append(path)

            return base_to_exp, g.node.keys()

        log().info('Game suggestion:')

        if not separate_exp:
            max_scores = {}
            graph, nodes = build_exp_graph()
            for base, exps in graph.items():
                if len(exps) == 0:
                    continue

                exp_max_score = self.__evaluations.get(base, 0.0)
                for exp in exps:
                    exp_max_score = max([exp_max_score] + [self.__evaluations[game_id] for game_id in exp if game_id in self.__evaluations])

                max_scores[base] = exp_max_score

            new_eval = self.__evaluations.copy()
            for game_id in nodes:
                if game_id not in graph:
                    new_eval.pop(game_id)
                else:
                    new_eval[game_id] = max_scores[game_id]

            sorted_evaluation = sorted(new_eval.items(), key=operator.itemgetter(1), reverse=True)

            if limit:
                sorted_evaluation = sorted_evaluation[:limit]

            for game_id, score in sorted_evaluation:
                if game_id in self.__evaluations:
                    log().info('\t%s [%f]' % (self.__collection[game_id].name, standardize(self.__evaluations[game_id])))
                    if game_id in self.__detailed_evaluations:
                        log().debug('\tDetailed evaluation for base game:')
                        for key in self.__detailed_evaluations[game_id]:
                            log().debug('\t\t%s = %s' % (key, str(self.__detailed_evaluations[game_id][key])))
                        log().debug('')
                else:
                    log().info('\t%s (you must use an expansion to play this game)' % self.__collection[game_id].name)

                if game_id in graph:
                    exps = set([])
                    for elist in graph[game_id]:
                        for e in elist:
                            exps.add(e)
                    for e in exps:
                        if e == game_id:
                            continue

                        log().info('\t\twith expansion %s [%f]' % (self.__collection[e].name, standardize(self.__evaluations[e])))
                        if e in self.__detailed_evaluations:
                            log().debug('\t\tDetailed evaluation:')
                            for key in self.__detailed_evaluations[e]:
                                log().debug('\t\t%s = %s' % (key, str(self.__detailed_evaluations[e][key])))
                            log().debug('')
        else:
            sorted_evaluation = sorted(self.__evaluations.items(), key=operator.itemgetter(1), reverse=True)

            if limit:
                sorted_evaluation = sorted_evaluation[:limit]

            for game_id, score in sorted_evaluation:
                log().info('\t%s [%f]' % (self.__collection[game_id].name, standardize(score)))
                for key in self.__detailed_evaluations[game_id]:
                    log().debug('\t\t%s = %s' % (key, str(self.__detailed_evaluations[game_id][key])))

# EXECUTION FUNCTIONS


def __create_and_parse_arguments():
    """
    This method will create and run an argument parser

    :return: parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="""
            Help board game players to choose the best games using BoardGameGeek data.
            BGG users and games stats are cached locally to reduce API usage and
            to allow offline suggestions.""",
        epilog='BoardGameGeek XML API Terms of use: https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use'
    )
    game_group = parser.add_argument_group('Game')
    game_group.add_argument('-t', '--time', help='Indicative playing time in minutes', type=int, default=0)
    game_group.add_argument('-w', '--weight', help='Indicative game weight', type=float, default=0.0)

    players_group = parser.add_argument_group('Players')
    players_group.add_argument('-u', '--username', nargs='+', help='BGG username of players')
    players_group.add_argument('-g', '--guests', help='How many guests (not BGG users) are present?', type=int, default=0)

    collection_group = parser.add_argument_group('Collection')
    collection_group.add_argument('-c', '--collection', nargs='+', help='Suggests only games owned by given BGG usernames (if omitted will choose from all players collections)')

    parser.add_argument('-d', '--debug', help='Print debug messages', action='store_true', default=False)
    parser.add_argument('-l', '--limit', help='Limit to how many results', type=int, default=0)
    parser.add_argument('-f', '--force', help='Re-download all data from BoardGameGeek site', action='store_true', default=False)
    parser.add_argument('-e', '--expansions', help='List expansion as separate games', action='store_true', default=False)

    args = parser.parse_args()

    # Clean
    if args.username:
        args.username = [username.strip() for username in args.username if username.strip() != '']

    if args.collection:
        args.collection = [username.strip() for username in args.collection if username.strip() != '']

    # Validation
    if (args.username is None) & (args.guests <= 0):
        parser.error('argument -u/--username & -g/--guests: at least one player (or guest) must be specified')

    if (args.username is None) & (args.collection is None):
        parser.error('argument -u/--username & -c/--collection: at least one BGG username must be specified')

    if args.time < 0:
        parser.error('argument -t/--time: time must be a positive value')

    if (args.weight < 0.0) | (args.weight > 5.0):
        parser.error('argument -w/--weight: weight must be a value between 0.0 and 5.0')

    return args


def setup_log(debug_enable):
    """
    Setup script logger

    :param debug_enable: Enable debug messages
    """
    logging_level = logging.DEBUG if debug_enable else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

    logging.getLogger('BoardGameGeekSuggestion').setLevel(logging_level)
    logging.getLogger('BoardGameGeekSuggestion').addHandler(handler)


def log():
    """
    Get script default logger

    :return: The script logger
    """
    return logging.getLogger('BoardGameGeekSuggestion')


if __name__ == '__main__':
    # Check version and libs
    if sys.version_info[0] < 3:
        print('Python 2.x is not supported, run with Python 3 (python3)')
        exit(1)

    try:
        import requests
    except ImportError:
        print('Missing Requests lib, use \'pip3 install requests\'')
        exit(1)
    try:
       from bs4 import BeautifulSoup
    except ImportError:
        print('Missing BeautifulSoup lib, use \'pip3 install beautifulsoup4\'')
        exit(1)
    try:
        import networkx
    except ImportError:
        print('Missing NetworkX lib, use \'pip3 install networkx\'')
        exit(1)

    # Setup
    arguments = __create_and_parse_arguments()
    setup_log(arguments.debug)

    # Call master
    master = Master(arguments.force)

    # Explain the situation to master
    if arguments.username:
        master.add_known_players(arguments.username)

    if arguments.guests > 0:
        master.add_guests(arguments.guests)

    if arguments.collection:
        # Tell master to use only games from some player / other people
        master.use_games_owned_by_these_players(arguments.collection)
    else:
        # Tell master to use games owned by players
        master.use_games_owned_by_these_players(arguments.username)

    # Tell master to rate every games
    master.rate_our_games(
        playing_time=(arguments.time if arguments.time > 0 else None),
        weight=(arguments.weight if arguments.weight > 0 else None)
    )

    # Print master suggestions
    master.show_your_decision(
        limit=(arguments.limit if arguments.limit > 0 else None),
        separate_exp=arguments.expansions
    )