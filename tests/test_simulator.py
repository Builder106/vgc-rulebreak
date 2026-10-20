from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.protocol import BattleCommand, parse_message_line


def test_battle_command_format() -> None:
    start_cmd = BattleCommand.start("gen9customgame", seed=(1, 2, 3, 4))
    assert start_cmd == '>start {"formatid": "gen9customgame", "seed": [1, 2, 3, 4]}'

    player_cmd = BattleCommand.player("p1", "Alice", "Pikachu|||||")
    assert player_cmd == '>player p1 {"name": "Alice", "team": "Pikachu|||||"}'

    choose_cmd = BattleCommand.choose("p1", "move 1")
    assert choose_cmd == ">p1 move 1"


def test_parse_message_line() -> None:
    assert parse_message_line("") is None
    assert parse_message_line("not a protocol line") is None

    turn_msg = parse_message_line("|turn|1")
    assert turn_msg is not None
    assert turn_msg.msg_type == "turn"
    assert turn_msg.args == ("1",)

    damage_msg = parse_message_line("|-damage|p1a: Annihilape|85/100|[from] item: Life Orb")
    assert damage_msg is not None
    assert damage_msg.msg_type == "-damage"
    assert damage_msg.args == ("p1a: Annihilape", "85/100")
    assert damage_msg.kwargs == {"from": "item: Life Orb"}


class MockBattleStream:
    """Mock BattleStream that returns pre-scripted lines on read_line."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.sent: list[str] = []

    def send(self, command: str) -> None:
        self.sent.append(command)

    def read_line(self, timeout: float = 5.0) -> str | None:
        if not self.responses:
            return None
        return self.responses.pop(0)

    def close(self) -> None:
        pass


def test_battle_session_with_mock_stream() -> None:
    mock_responses = [
        "|gametype|singles",
        "|split|p1",
        '|request|{"active": [{"moves": [{"id": "tackle", "pp": 35}]}]}',
        "|split|p2",
        '|request|{"active": [{"moves": [{"id": "tackle", "pp": 35}]}]}',
        "|turn|1",
        "|win|Alice",
    ]
    stream = MockBattleStream(mock_responses)
    session = BattleSession(stream)

    msgs = session.start("gen9customgame", "Alice", "TeamA", "Bob", "TeamB")
    assert len(msgs) > 0
    assert session.p1_request is not None
    assert session.p1_request["active"][0]["moves"][0]["id"] == "tackle"

    # Step to execute the turn
    step_result = session.step("move 1", "move 1")
    assert session.is_ended is True
    assert session.winner == "Alice"
    assert session.turn == 1
    assert step_result.is_ended is True
    assert step_result.winner == "Alice"
