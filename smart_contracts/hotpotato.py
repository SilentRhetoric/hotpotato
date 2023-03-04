from beaker import Application, Authorize
import beaker
from pyteal import App, Approve, Assert, Balance, Bytes, BytesZero, Div, Expr, Global, InnerTxnBuilder, Int, Seq, TealType, Txn, TxnField, TxnType, abi
import pyteal


class HotPotatoState:
    burnTimestamp = beaker.GlobalStateValue(pyteal.TealType.uint64)
    currentPot = beaker.GlobalStateValue(pyteal.TealType.uint64,default=Int(1_000_000))
    numPlayers = beaker.GlobalStateValue(pyteal.TealType.uint64, default=Int(0))
    currentHolder = beaker.GlobalStateValue(pyteal.TealType.bytes, default=Global.zero_address())
    for i in range(50):
        globals()[f"player{i+1}"] = beaker.GlobalStateValue(pyteal.TealType.bytes,f"player{i+1}")
    registered = beaker.LocalStateValue(TealType.bytes,default=Bytes("N"))


app = Application("HotPotato", state=HotPotatoState())


@app.create
def create() -> Expr:
    return Approve()

@app.external
def enterGame(payment: abi.PaymentTransaction, player: abi.String) -> Expr:
    return Seq(
        app.state.registered.set(Bytes("Y")),
        Assert(payment.get().amount() == app.state.currentPot.get()),
        Assert(payment.get().receiver() == Global.current_application_address()),
        Assert(App.globalGet(player.encode()) == Global.zero_address(), comment="Player slot is empty"),
        app.state.numPlayers.set(app.state.numPlayers.get() + Int(1))
    )

@app.external
def tossPotato(player: abi.String, recipient: abi.Address) -> Expr:
    return Seq(
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        Assert(Global.latest_timestamp() >= app.state.burnTimestamp.get()),
        Assert(App.globalGet(player.encode()) != app.state.currentHolder.get(), comment="Recipient is player in game"),
        Assert(recipient.get() != Txn.sender(), comment="Recipient is not sender"),
        app.state.currentHolder.set(recipient.get())
    )

@app.external
def grabPotato(player: abi.String, recipient: abi.Address) -> Expr:
    return Seq(
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        Assert(Global.latest_timestamp() < app.state.burnTimestamp.get()),
        Assert(App.globalGet(player.encode()) != app.state.currentHolder.get(), comment="Recipient is player in game"),
        Assert(recipient.get() != Txn.sender(), comment="Recipient is not sender"),
        app.state.currentHolder.set(recipient.get()),
        app.state.currentPot.set(Div(app.state.currentPot.get(),app.state.numPlayers.get()))
    )

@app.external
def exitGame(player: abi.String) -> Expr:
    return Seq(
        Assert(app.state.registered.get() == Bytes("Y"),comment="Account is registered in the game"),
        app.state.registered.set(Bytes("N")),
        Assert(App.globalGet(player.encode()) == Txn.sender() , comment="Account is in player slot"),
        App.globalPut(player.encode(),BytesZero(Int(32))),
        app.state.numPlayers.set(app.state.numPlayers.get() - Int(1)),
        InnerTxnBuilder.Execute(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: app.state.currentPot.get(),
                TxnField.receiver: Txn.sender(),
                TxnField.fee: Int(0),
                TxnField.note: Bytes("Thanks for playing!")
            }
        )
    )

@app.delete(authorize=Authorize.only(Global.creator_address()))
def delete() -> Expr:
    return Seq(
        Assert(app.state.numPlayers.get() == Int(0), comment="Zero players in game"),
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
