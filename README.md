#BGG Boardgame Suggestion
===
This is a (not very) simple script written in python which tries to make game advices.

To make this possibile the script will take users and games stats from [BoardGameGeek](https://www.boardgamegeek.com/) and, with some empirical calculations, it will produce a score. Using this score the script will propose a ranked list of games for your game sessions.

##How it works
    usage: bgs.py [-h] [-t TIME] [-w WEIGHT] [-u USERNAME [USERNAME ...]]
                  [-g GUESTS] [-c COLLECTION [COLLECTION ...]] [-d] [-l LIMIT]
                  [-f] [-e]

    Help board game players to choose the best games using BoardGameGeek data.
    BGG users and games stats are cached locally to reduce API usage and
    to allow offline suggestions.

    optional arguments:
      -h, --help            show this help message and exit
      -d, --debug           Print debug messages
      -l LIMIT, --limit LIMIT
                            Limit to how many results
      -f, --force           Re-download all data from BoardGameGeek site
      -e, --expansions      List expansion as separate games

    Game:
      -t TIME, --time TIME  Indicative playing time in minutes
      -w WEIGHT, --weight WEIGHT
                            Indicative game weight

    Players:
      -u USERNAME [USERNAME ...], --username USERNAME [USERNAME ...]
                            BGG username of players
      -g GUESTS, --guests GUESTS
                            How many guests (not BGG users) are present?

    Collection:
      -c COLLECTION [COLLECTION ...], --collection COLLECTION [COLLECTION ...]
                            Suggests only games owned by given BGG usernames (if
                            omitted will choose from all players collections)

    BoardGameGeek XML API Terms of use:
    https://boardgamegeek.com/wiki/page/XML_API_Terms_of_Use
   
Let's say that me and my five friends will have a short games session:

    > python3 bgs.py -u daktales -g 5 -t 30
    [INFO] Adding BGG players ..
    [INFO] Loaded daktales from cache
    [INFO] Adding guests ..
    [INFO] Adding player game collections ..
    [INFO] Loaded daktales from cache
    [INFO] Loading games data from cache ..
    [INFO] Game suggestion:
    [INFO]  Escape from the Aliens in Outer Space [0.759300]
    [INFO]  Escape: The Curse of the Temple (you must use an expansion to play this game)
    [INFO]    with expansion Escape: Illusions [0.612600]
    [INFO]  Parade [0.376000]

So the script suggests me to escape from the aliens, a short game recommended for six player and it doesn't suggest parade which is too long and not so recommended in six players.
## Install
* Download this project
* Install python 3 if you don't have it
* Install requests, beatifulsoup4 and networkx with pip3
* Done



## Tuning
The game evaluations is under testing so if you try this script and think that somethings is wrong use `-d` option and open an issue with your data. I'll try my best to improve this script.