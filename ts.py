import re
import string
import urllib.request
import time
import sys
import pickle
import argparse

import trueskill as ts


class Match: 
    def __init__(self, match_id):
        self.id = 0
        self.date = 0
        self.game = '?'
        self.goal = '?'
        self.players = []
        self.times = []
        self.blind = []

        url = urllib.request.urlopen('http://api.speedrunslive.com/pastraces/%d?callback=renderRace' % match_id)
        data = str(url.read())
        data = data.replace('\"', '')
        data = data.replace(',', '')
        data = data.split('\\n')
        for line in data:
            parts = line.split(' : ')
            if len(parts) != 2:
                continue
            if parts[0] == 'name':
                self.game = parts[1]
            if parts[0] == 'goal':
                self.goal = parts[1]
            if parts[0] == 'id' and self.id == 0:
                self.id = int(parts[1])
            if parts[0] == 'date':
                self.date = int(parts[1])
            if parts[0] == 'player':
                self.players += [parts[1]]
            if parts[0] == 'time':
                self.times += [int(parts[1])]
            if parts[0] == 'oldtrueskill':
                self.blind += [parts[1] == '0']

        self.times = [t if t > 0 else 1e9 for t in self.times]

    def __str__(self):
        return 'ID: ' + str(self.id) + ' Game: ' + self.game + ' Goal: ' + self.goal

    def sort_players(self):
        order = list(range(len(self.players)))
        order = sorted(order, key=lambda x: self.times[x])
        self.players = [self.players[i] for i in order]
        self.times = [self.times[i] for i in order]
        self.blind = [self.blind[i] for i in order]


def get_id_set(data):
    id_set = set()
    for line in data:
        search = re.search('http://.*speedrunslive.com/races/result/#!/([0-9]+)', line)
        if search:
            id_set.add(int(search.group(1)))
        search = re.search('^([0-9]+)$', line)
        if search:
            id_set.add(int(search.group(1)))
    return id_set


def scrape_matches(id_set, delay=0.2):
    matches = []
    for match_id in id_set:
        print('\rScraping %d / %d matches... ' % (len(matches), len(id_set)), end='', file=sys.stderr)
        sys.stderr.flush()
        matches += [Match(match_id)]
        time.sleep(delay)
    print('\rScraping Done!                         ', file=sys.stderr)

    return matches


def save_matches(matches, path):
    with open(path, 'wb') as f:
        pickle.dump(matches, f)


def load_matches(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


# Globals
args = None


# Helper Functions
def extract_all_players(matches):
    players = set()
    for match in matches:
        for player in match.players:
            players.add(player)
    return list(players)


# Generate Various Stats
def generate_true_skill(matches):
    matches_no = {}
    forfeits_no = {}
    for match in matches:
        for i, player in enumerate(match.players):
            matches_no[player] = matches_no.get(player, 0) + 1
            forfeits_no[player] = forfeits_no.get(player, 0) + (1 if match.times[i] >= 1e9 else 0)

    ts.setup(tau=args.tau, draw_probability=args.drawprob)
    players = extract_all_players(matches)
    ratings = {player: ts.Rating() for player in players}
    for match in matches:
        m_ratings = [{match.players[i]: ratings[match.players[i]]} for i in range(len(match.players))]
        ranks = [0] * len(match.players)
        for i in range(1, len(match.players)):
            if match.times[i] == match.times[i-1]:
                ranks[i] = ranks[i-1]
            elif match.times[i] > match.times[i-1]:
                ranks[i] = ranks[i-1] + 1
        new_ratings = ts.rate(m_ratings, ranks=ranks)
        new_ratings = {k: v for d in new_ratings for k, v in d.items()}
        for player, new_rating in new_ratings.items():
            ratings[player] = new_rating

    players = sorted(players, key=lambda p: ratings[p].mu - args.sigmaweight * ratings[p].sigma, reverse=True)

    if args.addheader:
        columns = ['Player', 'Rating', 'Mu', 'Sigma', '#Matches', '#Forfeits']
        if args.addplace:
            columns.insert(0, 'Place')
        print(*columns, sep=args.delim)

    place = 1
    for player in players:
        if matches_no[player] < args.minmatches:
            continue
        rating = ratings[player]
        row = [player, round(rating.mu - args.sigmaweight * rating.sigma, 3), round(rating.mu, 3), round(rating.sigma, 3), matches_no[player], forfeits_no[player]]
        if args.addplace:
            row.insert(0, place)
            place += 1
        print(*row, sep=args.delim)


def main():
    parser = argparse.ArgumentParser(description='description goes here')
    parser.add_argument('-d', '--download', help='scrapes SRL website in search of missing matches (please be nice to SRL and try to avoid it)', action='store_true')
    parser.add_argument('-s', '--save', help='saves parsed match data', action='store_true')
    parser.add_argument('-l', '--load', help='loads parsed match data', action='store_true')
    parser.add_argument('-r', '--removefarmers', help='removes farmers (players with non-zero rating before the match started) from match', action='store_true')
    parser.add_argument('-m', '--mergesub10', help='creates a tie between everyone with sub 10 time', action='store_true')
    parser.add_argument('-g', '--mergesamegoal', help='merges different matches with the same goal', action='store_true')
    parser.add_argument('--tau', help='changes default tau value (def: %(default)f)', type=float, default=0.01)
    parser.add_argument('--drawprob', help='changes default draw probability value (def: %(default)f)', metavar='P', type=float, default=0.1)
    parser.add_argument('--sigmaweight', help='changes default weight of sigma in rating calcution value (def: %(default)f)', metavar='W', type=float, default=1.5)
    parser.add_argument('--minmatches', help='minimum number of matches for players in order to be included (def: %(default)d)', type=int, default=6)
    parser.add_argument('--addheader', help='adds header to the generated file', action='store_true')
    parser.add_argument('--addplace', help='adds placement to the generated file', action='store_true')
    parser.add_argument('--delim', help='changes delimiter in generated file', default=' ')
    parser.add_argument('--add', help='list of additional match ids to add', metavar='ID', nargs='+', type=int, default=[])
    parser.add_argument('--rem', help='list of additional match ids to remove', metavar='ID', nargs='+', type=int, default=[])
    global args
    args = parser.parse_args()
    print(args, file=sys.stderr)

    matches = []

    if args.load:
        matches = load_matches('matches.data')

    if args.download:
        id_set = set()
        with open('matches.txt') as f:
            mt_list = f.readlines()
        id_set = get_id_set(mt_list)

        for id in args.add:
            id_set.add(id)

        for match in matches:
            id_set.discard(match.id)

        matches += scrape_matches(id_set)

    if args.rem:
        id_set = set(args.rem)
        matches = [match for match in matches if match.id not in id_set]

    if args.save:
        save_matches(matches, 'matches.data')

    if args.removefarmers:
        for match in matches:
            for i in reversed(range(len(match.players))):
                if not match.blind[i]:
                    del match.times[i]
                    del match.players[i]
                    del match.blind[i]

    if args.mergesub10:
        for match in matches:
            for i in range(len(match.times)):
                match.times[i] = max(match.times[i], 10 * 60)

    if args.mergesamegoal:
        similar_matches = {}
        for match in matches:
            h = match.game.lower() + '|' + match.goal.lower()
            if h not in similar_matches:
                similar_matches[h] = []
            similar_matches[h] += [match]
        matches = []
        for group in similar_matches.values():
            merged_match = group[0]
            for match in group[1:]:
                merged_match.date = max(merged_match.date, match.date)
                merged_match.times += match.times
                merged_match.players += match.players
                merged_match.blind += match.blind
            matches += [merged_match]

    matches = [match for match in matches if len(match.players) >= 2]

    for match in matches:
        match.sort_players()

    generate_true_skill(matches)


if __name__ == '__main__':
    main()
