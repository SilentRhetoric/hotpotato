from re import S
from turtle import st
from beaker import Application, Authorize
import beaker
from pyteal import App, Approve, Assert, AssetHolding, Balance, Bytes, BytesZero, Div, Expr, Global, If, InnerTxn, InnerTxnBuilder, Int, Pop, Return, Seq, Suffix, TealType, Txn, TxnField, TxnType, abi
import pyteal

class TossResult(abi.NamedTuple):
    current_pot: abi.Field[abi.Uint64]
    next_randomness_round: abi.Field[abi.Uint64]

class HotPotatoState:
    potato = beaker.GlobalStateValue(pyteal.TealType.uint64)
    randomness_round = beaker.GlobalStateValue(pyteal.TealType.uint64, default=Global.round())
    burn_timestamp = beaker.GlobalStateValue(pyteal.TealType.uint64, default=Global.latest_timestamp())
    current_pot = beaker.GlobalStateValue(pyteal.TealType.uint64,default=Int(1_000_000))
    num_players = beaker.GlobalStateValue(pyteal.TealType.uint64, default=Int(0))
    current_holder = beaker.GlobalStateValue(pyteal.TealType.bytes, default=Global.zero_address())
    for i in range(49):
        globals()[f"player{i+1}"] = beaker.GlobalStateValue(pyteal.TealType.bytes,f"player{i+1}")
    registered = beaker.LocalStateValue(TealType.bytes,default=Bytes("N"))


app = Application("HotPotato", state=HotPotatoState())

# https://developer.algorand.org/articles/usage-and-best-practices-for-randomness-beacon/?from_query=vrf
# https://github.com/algorand-devrel/coin-flipper/
# @pyteal.Subroutine(TealType.bytes)
# def get_randomness(round: Expr) -> Expr:
#     """requests randomness from random oracle beacon for requested round"""
#     return Seq(
#         # Prep arguments
#         (round_to_get := abi.Uint64()).set(round),
#         (user_data := abi.make(abi.DynamicArray[abi.Byte])).set([]),
#         # Get randomness from oracle
#         InnerTxnBuilder.ExecuteMethodCall(
#             app_id=Int(110096026),
#             method_signature="must_get(uint64,byte[])byte[]",
#             args=[round_to_get, user_data],
#         ),
#         # Remove first 4 bytes (ABI return prefix)
#         # and return the rest
#         Suffix(InnerTxn.last_log(), Int(4)),
#     )

@app.create
def create() -> Expr:
    return Seq(
         InnerTxnBuilder.Execute(
                {
                    TxnField.type_enum: TxnType.AssetConfig,
                    TxnField.config_asset_total: Int(1),
                    TxnField.config_asset_clawback: Global.current_application_address(),
                    TxnField.config_asset_decimals: Int(0),
                    TxnField.config_asset_default_frozen: Int(1),
                    TxnField.config_asset_freeze:  Global.current_application_address(),
                    TxnField.config_asset_manager: Global.current_application_address(),
                    TxnField.config_asset_reserve: Global.current_application_address(),
                    TxnField.fee: Int(0),
                }
            ),
        app.state.potato.set(InnerTxn.created_asset_id())
    )

@app.external
def enterGame(payment: abi.PaymentTransaction, player: abi.String) -> Expr:
    return Seq(
        app.state.registered.set(Bytes("Y")),
        Assert(payment.get().amount() == app.state.current_pot.get()),
        Assert(payment.get().receiver() == Global.current_application_address()),
        Assert(App.globalGet(player.encode()) == Global.zero_address(), comment="Player slot is empty"),
        Assert(app.state.num_players.get() < Int(49), comment="Less than 49 players"),
        app.state.num_players.set(app.state.num_players.get() + Int(1))
    )

@app.external
def tossPotato(player_slot: abi.String, recipient: abi.Account) -> Expr:
    return Seq(
        Assert(Global.latest_timestamp() <= app.state.burn_timestamp.get(), comment="Before burn time"),
        Assert(Txn.sender() == app.state.current_holder.get(), comment="Sender is current holder"),
        (holding_potato := AssetHolding().balance(Txn.sender(), app.state.potato.get())),
        Assert(holding_potato.hasValue(), comment="Current holder has potato"),
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        Assert(App.globalGet(player_slot.encode()) != app.state.current_holder.get(), comment="Recipient is another player"),
        Assert(recipient.address() != Txn.sender(), comment="Recipient is not sender"),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: app.state.potato.get(),
                TxnField.asset_amount: Int(1),
                TxnField.asset_sender: Txn.sender(),
                TxnField.asset_receiver: recipient.address(),
                TxnField.fee: Int(0),
                TxnField.note: Bytes("Spud tossed successfully!")
            }
        ),
        app.state.current_holder.set(recipient.address()),
        app.state.burn_timestamp.set(Global.latest_timestamp() + Int(100_000)),
        app.state.randomness_round.set(Global.round() + Int(8) - (Global.round() % Int(8)))
        )


@app.external
def grabPotato(player: abi.String, recipient: abi.Account) -> Expr:
    return Seq(
        Assert(Global.latest_timestamp() > app.state.burn_timestamp.get(), comment="After burn time"),
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        Assert(Txn.sender() != app.state.current_holder.get(), comment="Sender is not current holder"),
        Assert(App.globalGet(player.encode()) != app.state.current_holder.get(), comment="Recipient is another player"),
        Assert(recipient.address() != Txn.sender(), comment="Recipient is not sender"),
        App.localDel(app.state.current_holder.get(),Bytes("registered")),
                InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: app.state.potato.get(),
                TxnField.asset_amount: Int(1),
                TxnField.asset_sender: app.state.current_holder.get(),
                TxnField.asset_receiver: recipient.address(),
                TxnField.fee: Int(0),
                TxnField.note: Bytes("Spud tossed successfully!")
            }
        ),
        app.state.current_holder.set(recipient.address()),
        app.state.burn_timestamp.set(Global.latest_timestamp() + Int(100_000)),
        app.state.randomness_round.set(Global.round() + Int(8) - (Global.round() % Int(8))),
        # Burned player's entry fee is split 50 ways for 49 players + house
        app.state.current_pot.set(Div(app.state.current_pot.get(), Int(50))),
    )

@app.external
def exitGame(player: abi.String) -> Expr:
    return Seq(
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        app.state.registered.set(Bytes("N")),
        Assert(App.globalGet(player.encode()) == Txn.sender() , comment="Account is in player slot"),
        App.globalPut(player.encode(),BytesZero(Int(32))),
        app.state.num_players.set(app.state.num_players.get() - Int(1)),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: app.state.current_pot.get(),
                TxnField.receiver: Txn.sender(),
                TxnField.fee: Int(0),
                TxnField.note: Bytes("Thanks for playing!")
            }
        )
    )

@app.delete(authorize=Authorize.only(Global.creator_address()))
def delete() -> Expr:
    return Seq(
        Assert(app.state.num_players.get() == Int(0), comment="Zero players in game"),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: Balance(Global.current_application_address()),
                TxnField.receiver: Global.creator_address(),
                TxnField.close_remainder_to: Global.creator_address(),
                TxnField.fee: Int(0),
                TxnField.note: Bytes("Game closed!")
            }
        )
        )
