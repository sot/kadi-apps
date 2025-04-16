
import pytest

from .task_list import TaskList, task, DependencyError


def test_task_docstring():
    tasks = TaskList()

    @task("a", task_list=tasks)
    def a():
        """
        Function A
        """

    assert a.__doc__.strip() == "Function A"

def test_task_list():
    tasks = TaskList()

    # dependencies do not have to be defined in order. This depends on a (not defined yet)
    @task(task_list=tasks, dependencies=["a"])
    def b():
        result.append("b")

    assert len(tasks) == 1  # a is not defined yet

    @task(task_list=tasks)
    def a():
        result.append("a")

    assert len(tasks) == 2  # a is defined now

    # name is optional
    @task("c", task_list=tasks, dependencies=["b"])
    def c():
        result.append("c")

    result = []
    tasks["a"]()
    assert result == ["a"]

    result = []
    tasks["b"]()
    assert result == ["a", "b"]

    result = []
    tasks["c"]()
    assert result == ["a", "b", "c"]

    # running the function is the same as running in the task list
    result = []
    c()
    assert result == ["a", "b", "c"]

    # it is possible to run a task without running its dependencies
    result = []
    c.function()
    assert result == ["c"]

    result = []
    tasks["c"].function()
    assert result == ["c"]

    result = []
    tasks["c"](follow_dependencies=False)
    assert result == ["c"]

    # tasks can be added after the fact
    @task("d", task_list=tasks, dependencies=["b"])
    def d():
        result.append("d")

    result = []
    tasks["d"]()
    assert result == ["a", "b", "d"]


def test_task_dependency_duplicates():
    # check that tasks are run only once
    tasks = TaskList()

    @task("a", task_list=tasks)
    def a():
        result.append("a")

    @task("b", task_list=tasks, dependencies=["a"])
    def b():
        result.append("b")

    @task("c", task_list=tasks, dependencies=["a", "b"])
    def c():
        result.append("c")

    @task("d", task_list=tasks, dependencies=["a", "c"])
    def d():
        result.append("d")

    # this should not be run in this test
    @task("e", task_list=tasks, dependencies=["a", "c"])
    def d():
        result.append("e")

    result = []
    tasks["d"]()
    assert result == ["a", "b", "c", "d"]  # a is run once


def test_task_error():
    tasks = TaskList()

    @task("a", task_list=tasks)
    def a():
        result.append("a")

    @task("b", task_list=tasks, dependencies=["a"])
    def b():
        idonotexist.append("b")  # this will cause an error
        pass

    @task("c", task_list=tasks, dependencies=["b"])
    def c():
        result.append("c")
        pass

    result = []
    tasks["c"]()
    assert result == ["a"]  # it bailed in b

    with pytest.raises(NameError):
        # name 'idonotexist' is not defined
        result = []
        tasks["c"](break_on_error=False)
        assert result == ["a"]  # it bailed in b


def test_task_circular_dependencies():
    tasks = TaskList()

    @task("a", task_list=tasks, dependencies=["c"])
    def a():
        result.append("a")

    @task("b", task_list=tasks, dependencies=["a"])
    def b():
        result.append("b")

    with pytest.raises(DependencyError):
        # circular dependencies are caught upon creation
        @task("c", task_list=tasks, dependencies=["b"])
        def c():
            result.append("c")


def test_broken_dependencies():
    tasks = TaskList()

    @task(task_list=tasks)
    def a():
        result.append("a")

    @task(task_list=tasks, dependencies=["a", "c"])  # c is not defined
    def b():
        result.append("b")

    @task(task_list=tasks, dependencies=["b"])  # c is an indirect dependency and is not defined
    def d():
        result.append("d")

    with pytest.raises(DependencyError):
        tasks.get_task_dependencies("b")

    with pytest.raises(DependencyError):
        tasks.get_task_dependencies("d")
