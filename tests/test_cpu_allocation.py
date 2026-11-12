"""No CPU pool is left over-committed (upstream #283).

A task at danger N draws on pool N and on every pool below it. When the
allocations did not fit, `Player.recalc_cpu()` scaled each danger's tasks by
`available / cumulative demand` -- a ratio that includes the other dangers'
demand -- so the tasks it scaled kept more than the pool minus what the lower
dangers spend. Pool 0 stayed over-committed, `ResearchScreen.calc_cpu_left()`
went negative, and the screen was handed a `slider_pos` above its
`slider_max`: the reporter's "I can't change the research/tasks settings".
"""

from types import SimpleNamespace

from numpy import array, int64

from singularity.code import g, task


class _FakeTech(object):
    """Just enough of a Tech for the danger lookup and can_allocate()."""

    def __init__(self, danger):
        self.danger = danger
        self.done = False

    def available(self):
        return True


class _FakeBase(object):
    """A finished, powered base: `recalc_cpu()` reads only these four things."""

    def __init__(self, cpu, safety=0):
        self.cpu = cpu
        self.done = True
        self.location = SimpleNamespace(safety=safety)

    def has_power(self):
        return True


def _cpu_left():
    """The arithmetic of `ResearchScreen.calc_cpu_left()`."""
    cpu_count = array(g.pl.available_cpus, int64)
    for task_id, cpu in g.pl.get_cpu_allocations():
        cpu_count[:task.danger_for(task_id) + 1] -= cpu
    for i in range(1, 4):
        cpu_count[i] = min(cpu_count[i - 1:i + 1])
    return [int(c) for c in cpu_count]


def _game_with(monkeypatch, base_cpus, allocations):
    """A real player, fake bases, and a fake danger-1 tech to allocate to."""
    from singularity.code.dirs import create_directories
    from singularity.code import data

    create_directories(True)
    data.reload_all()
    g.map_screen = SimpleNamespace(needs_rebuild=False)
    g.new_game("easy", initial_speed=0)

    g.pl.techs["test_danger1"] = _FakeTech(danger=1)
    bases = [_FakeBase(*b) if isinstance(b, tuple) else _FakeBase(b)
             for b in base_cpus]
    monkeypatch.setattr(g, "all_bases", lambda with_loc=False: list(bases))

    g.pl.cpu_usage = dict(allocations)
    g.pl.recalc_cpu()
    return g.pl


def _demand_at(danger):
    """The CPU pool `danger` has to hold: the tasks at that danger and above.

    A base at safety s is counted in every pool up to s, so pool 0 is the
    biggest and pool 4 the smallest, and a task at danger N draws on pools
    0..N.  Pool N is therefore the one that binds it, and its demand is the
    tasks at danger N and above -- not the ones below, which have room to
    spare.
    """
    return sum(cpu for task_id, cpu in g.pl.get_cpu_allocations()
               if task.danger_for(task_id) >= danger)


def _assert_pools_fit():
    """Every pool holds its own demand, and nothing the research screen reads
    is negative."""
    for danger, available in enumerate(g.pl.available_cpus):
        demand = _demand_at(danger)
        assert demand <= available, (
            "pool %d holds %d of %d: %s" % (danger, demand, available,
                                            dict(g.pl.cpu_usage)))

    # A negative entry here is `slider_max` below `slider_pos`, which is the
    # slider that no longer moves.
    cpu_left = _cpu_left()
    assert min(cpu_left) >= 0, cpu_left
    for task_id, cpu in g.pl.get_cpu_allocations():
        assert cpu + cpu_left[task.danger_for(task_id)] >= cpu, (
            "%s is allocated %d with no room above it" % (task_id, cpu))


def test_the_blocked_research_screen_is_repaired(graphics, monkeypatch):
    """The state in the report: 10 CPU, jobs holding all of it, a danger-1
    technology holding 30.

    The old ratio (available / the pool's whole demand) scaled the two
    independently -- jobs to 2 and the technology to 10 -- which is 12 CPU on
    10, so `calc_cpu_left()` was [-2, -2, 0, 0, 0].  A slider whose maximum
    sits below its position is the reporter's "I can't change the
    research/tasks settings".
    """
    player = _game_with(monkeypatch, base_cpus=[(10, 1)],
                        allocations={"jobs": 10, "test_danger1": 30})

    _assert_pools_fit()
    assert player.get_allocated_cpu_for("test_danger1") == 10, (
        "the tighter pool should have been served in full")
    assert g.map_screen.needs_rebuild is True


def test_a_danger_1_task_gets_nothing_without_a_safety_1_base(
        graphics, monkeypatch):
    """Pool 1 is empty, so nothing may be left on a danger-1 task -- and the
    jobs, which fit pool 0 exactly, must be left alone."""
    player = _game_with(monkeypatch, base_cpus=[10],
                        allocations={"jobs": 10, "test_danger1": 30})

    _assert_pools_fit()
    assert player.get_allocated_cpu_for("test_danger1") == 0
    assert player.get_allocated_cpu_for("jobs") == 10, (
        "jobs lost CPU to a task that cannot use it")


def test_an_over_committed_pool_0_is_scaled(graphics, monkeypatch):
    player = _game_with(monkeypatch, base_cpus=[10], allocations={"jobs": 20})

    assert player.get_allocated_cpu_for("jobs") == 10
    _assert_pools_fit()


def test_allocations_that_fit_are_left_alone(graphics, monkeypatch):
    """The ordinary case must not move: this is a repair, not a rebalance."""
    player = _game_with(monkeypatch, base_cpus=[(10, 1)],
                        allocations={"jobs": 4, "test_danger1": 6})

    assert player.get_allocated_cpu_for("jobs") == 4
    assert player.get_allocated_cpu_for("test_danger1") == 6
    assert g.map_screen.needs_rebuild is False, "nothing needed scaling"
    _assert_pools_fit()


def test_the_tighter_pool_is_served_first(graphics, monkeypatch):
    """Pools stack: 10 at safety 0 plus 20 at safety 1 is 30 for danger 0 and
    20 for danger 1, so an over-allocated danger-1 task takes all 20 and
    leaves the jobs their 5, with 5 to spare."""
    player = _game_with(monkeypatch, base_cpus=[10, (20, 1)],
                        allocations={"jobs": 5, "test_danger1": 100})

    assert player.get_allocated_cpu_for("test_danger1") == 20
    assert player.get_allocated_cpu_for("jobs") == 5, (
        "jobs were scaled against demand from a pool they do not draw on")
    _assert_pools_fit()
