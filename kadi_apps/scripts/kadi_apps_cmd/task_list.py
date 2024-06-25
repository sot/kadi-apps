
import networkx as nx
import functools


class TaskList:
    """
    Class to manage a list of tasks.
    
    Task dependencies are represented internally as a directed acyclic graph.
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def check(self):
        if not nx.is_directed_acyclic_graph(self.graph):
            msg = "Actions have circular dependencies"
            for cycle in nx.simple_cycles(self.graph):
                msg += f"\n  {cycle}"
            raise RuntimeError(msg)

    def function(self, name):
        return self.graph.nodes[name]["function"]
    
    def tasks(self):
        return list(self.graph.nodes)

    def run(self, name, follow_dependencies=True, break_on_error=True):
        """Run a task and its dependencies."""
        tasks = []
        if follow_dependencies:
            tasks += [
                        task for task in nx.topological_sort(self.graph)
                        if task in nx.ancestors(self.graph, name)
                    ]
        tasks += [name]
        for task in tasks:
            try:
                self.graph.nodes[task]["function"]()
            except Exception as e:
                print(f"Error running {task}: {e}")
                if break_on_error:
                    break
                else:
                    raise

    def task(self, name, dependencies=None):
        """Decorator for script actions."""
        def decorator(func):
            self.graph.add_node(name, function=func)
            for dep in dependencies or []:
                self.graph.add_edge(dep, name)
            @functools.wraps(func)
            def wrapped_function():
                self.run(name)
            return wrapped_function
        return decorator