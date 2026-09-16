
import networkx as nx
import functools
import inspect
from collections.abc import MutableMapping


class DependencyError(Exception):
    pass


class TaskList(MutableMapping):
    """
    Class to keep track of dependencies in a list of tasks.
    
    Task dependencies are represented internally as a directed acyclic graph.
    """
    def __init__(self):
        self.graph = nx.DiGraph()

        # this holds dependencies that are added to the graph before the task
        # is added. These are fixed when the task is added to the graph.
        # otherwise, a node is automatically added without a task
        # we keep track of this to give an error early, and so nodes are sorted as they are added. 
        self.broken_dependencies = set()

    def _check_(self):
        """Sanity checks."""
        if not nx.is_directed_acyclic_graph(self.graph):
            msg = "Actions have circular dependencies"
            for cycle in nx.simple_cycles(self.graph):
                msg += f"\n  {cycle}"
            raise DependencyError(msg)

    def get_task_dependencies(self, name):
        """
        All the dependencies of a task (not including the task itself).

        The dependencies include indirect dependencies.
        """
        dependencies = [
            task for task in nx.topological_sort(self.graph)
            if task in nx.ancestors(self.graph, name)
        ]

        broken_dependencies = {
            dep for (dep, name) in self.broken_dependencies if name in dependencies + ["b"]
        }
        if broken_dependencies:
            raise DependencyError(f"{name} has broken dependencies: {', '.join(broken_dependencies)}")
        return dependencies

    def __getitem__(self, key):
        return self.graph.nodes[key]["task"]
    def __setitem__(self, name, task):
        assert task.name == name
        self.graph.add_node(name, task=task, function=task.function)
        # these are dependencies that were added before the task was added. Can be fixed now.
        fix_dependencies = [(dp, nm) for (dp, nm) in self.broken_dependencies if dp == name]
        for dep, name in fix_dependencies:
            self.graph.add_edge(dep, name)
            self.broken_dependencies.remove((dep, name))
        for dep in task.explicit_dependencies or []:
            if dep in self.graph.nodes:
                self.graph.add_edge(dep, name)
            else:
                self.broken_dependencies.add((dep, name))
        self._check_()
    def __delitem__(self, key):
        self.graph.remove_node(key)
    def __len__(self):
        return len(self.graph.nodes)
    def __iter__(self):
        return self.graph.nodes.__iter__()
    def __contains__(self, key):
        return key in self.graph.nodes


class Task:
    def __init__(self, name, function, dependencies=None, task_list=None):
        self.name = name
        self._dependencies = [] if dependencies is None else dependencies
        self.function = function
        self.task_list = TASK_LIST if task_list is None else task_list

        self.task_list[name] = self

    @property
    def explicit_dependencies(self):
        return self._dependencies

    @property
    def all_dependencies(self):
        return self.task_list.get_task_dependencies(self.name)

    def __call__(self, follow_dependencies=True, break_on_error=True):
        tasks = []
        if follow_dependencies:
            tasks += self.all_dependencies
        tasks += [self.name]
        for task in tasks:
            try:
                self.task_list[task].function()
            except Exception as e:
                print(f"Error running {task}: {e}")
                if break_on_error:
                    break
                else:
                    raise


def task(name=None, dependencies=None, task_list=None):
    """Decorator for script actions."""

    def decorator(func, name=name, dependencies=dependencies, task_list=task_list):
        if not inspect.isfunction(func):
            raise ValueError("Task must be a function")
        if name is None:
            name = func.__name__.replace("_", "-")
        if not isinstance(name, str):
            raise ValueError(f"Task name for {func.__name__} must be a string, not {type(name)}")
        task = Task(name, func, dependencies=dependencies, task_list=task_list)
        functools.update_wrapper(task, func)
        return task

    if inspect.isfunction(name):
        # this is a decorator without arguments
        task = decorator(name, name=name.__name__.replace("_", "-"))
        return task

    return decorator


TASK_LIST = TaskList()
