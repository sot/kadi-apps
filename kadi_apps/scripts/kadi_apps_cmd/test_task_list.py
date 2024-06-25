
import pytest

from .task_list import TaskList


def test_task_docstring():
    tasks = TaskList()

    @tasks.task("a")
    def a():
        """
        Function A
        """
        pass

    assert a.__doc__.strip() == "Function A"

def test_task_list():
    tasks = TaskList()

    # dependencies do not have to be defined in order
    @tasks.task("b", dependencies=["a"])
    def b():
        result.append("b")

    @tasks.task("a")
    def a():
        result.append("a")

    @tasks.task("c", dependencies=["b"])
    def c():
        result.append("c")

    tasks.check()

    result = []
    tasks.run("a")
    assert result == ["a"]

    result = []
    tasks.run("b")
    assert result == ["a", "b"]

    result = []
    tasks.run("c")
    assert result == ["a", "b", "c"]

    # running the function is the same as running in the task list
    result = []
    c()
    assert result == ["a", "b", "c"]

    # it is possible to run a task without running its dependencies
    result = []
    tasks.run("c", follow_dependencies=False)
    assert result == ["c"]

    # tasks can be added after the fact
    @tasks.task("d", dependencies=["b"])
    def d():
        result.append("d")

    result = []
    tasks.run("d")
    assert result == ["a", "b", "d"]


def test_task_dependency_duplicates():
    tasks = TaskList()

    @tasks.task("a")
    def a():
        result.append("a")

    @tasks.task("b", dependencies=["a"])
    def b():
        result.append("b")

    @tasks.task("c", dependencies=["a", "b"])
    def c():
        result.append("c")

    @tasks.task("d", dependencies=["a", "c"])
    def d():
        result.append("d")

    # this should not be run in this test
    @tasks.task("e", dependencies=["a", "c"])
    def d():
        result.append("e")

    tasks.check()

    result = []
    tasks.run("d")
    assert result == ["a", "b", "c", "d"]  # a is run once


def test_task_error():
    tasks = TaskList()

    @tasks.task("a")
    def a():
        result.append("a")

    @tasks.task("b", dependencies=["a"])
    def b():
        idonotexist.append("b")
        pass

    @tasks.task("c", dependencies=["b"])
    def c():
        result.append("c")
        pass

    tasks.check()

    result = []
    tasks.run("c")
    assert result == ["a"]  # it bailed in b

    with pytest.raises(NameError):
        # name 'idonotexist' is not defined
        tasks.run("c", break_on_error=False)


def test_task_circular_dependencies():
    tasks = TaskList()

    @tasks.task("a", dependencies=["c"])
    def a():
        result.append("a")

    @tasks.task("b", dependencies=["a"])
    def b():
        result.append("b")

    @tasks.task("c", dependencies=["b"])
    def c():
        result.append("c")

    with pytest.raises(RuntimeError):
        tasks.check()

