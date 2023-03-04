# Hot Potato

## Front End

### UI Methods

1. Enter Game
   1. Opt into NFT
   2. Opt into app
   3. App Call
2. Toss Potato
3. Grab Potato
4. Exit Game
5. Create Game

## Contract

### State

1. potAmount
2. burnTimestamp
3. numPlayers
4. player1account  
   ...
5. player60account

### Contract Methods

1. create - Mint NFT w/ freeze & clawback, initialize state
2. enterGame - Check payment = pot size, add localState, add account to globalState
3. tossPotato - Check currentTime vs burnTime, check that next recipient is in game, clawback potato
4. grabPotato - Check currentTime > burnTime, pay out bonus to grabber (amount = potAmount / numPlayers), clawback potato from holder to next player
5. exitGame - Pay out potAmount to player and deregister account from localState & globalState
6. closeGame - Verify caller is creator, close balance to creator

## Game Types

1. One minute rounds, 1A to enter
2. One hour rounds, 25A to enter
