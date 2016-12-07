from pathlib import PurePath, Path
#from glob import glob
import json
import re
import sys

from igraph import Graph, ALL
import numpy as np

from sn.io import pickle, io_array
import sn.utils
from sn.utils import time as benchmark

_DEBUG_ = False

sn.utils._VERBOSE_ = True


def read(path: PurePath, *args, **kwds) -> Graph:
    try:
        g = Graph.Read(str(path), *args, **kwds)
        benchmark(message='Reading "{0}"'.format(path))
        try:
            print(path.parent.joinpath(path.stem + '.labels'))
            with open(str(path.parent.joinpath(path.stem + '.labels'))) as r:
                g.vs['label'] = [ re.sub(r'\n', '', line) for line in r.readlines()]
        except FileNotFoundError: pass
        return g
    except:
        print('Parsing failure:', path)
        e, message, trace = sys.exc_info()
        print(message)
        raise e


def normalize(g: Graph, profile: dict) -> Graph:
    graph_dir = PurePath(profile['root']).joinpath(profile['name'], 'graph')
    print('graph_dir:', graph_dir)

    adj_path = graph_dir.joinpath('adjacency')
    try:
        if profile['force']: raise FileNotFoundError
        return io_array(adj_path)
    except FileNotFoundError:
        benchmark(message='Starting normalize')
        # Convert to undirected graph
        g.to_undirected()
        assert not g.is_directed()
        benchmark(message='Converted to directed graph')

    # The largest strongly connected component
        g = max(g.decompose(maxcompno=1), key=(lambda g: len(g.vs)))
        benchmark(message='Maximum connected component')

        # Remove self-loops
        g.simplify()
        assert not any(g.is_loop())
        benchmark(message='Removed self-loops')

        profile['graph_size'] = [len(g.vs), len(g.es)]

        io_array(adj_path, g.get_adjlist())
        io_array(graph_dir.joinpath('edgelist'), g.get_edgelist())

        if not 'label' in g.vs.attributes(): g.vs['label'] = g.vs['id']
        if all([len(label) > 0 for label in g.vs['label']]):
            label_path = graph_dir.joinpath('label')
            io_array(label_path, g.vs['label'])
        return g


if __name__ == '__main__' and False:
    g = Graph([(0,1), (0,2), (2,3), (3,4), (4,2), (2,5), (5,0), (6,3), (5,6)])
    g.vs["name"] = ["Alice", "Bob", "Claire", "Dennis", "Esther", "Frank", "George"]
    print(g.vs['name'])
    print(g)
    print(g.vs[0])


if __name__ == '__main__' and False:
    g = Graph([(0,1), (0,0), (0,2), (2,3), (3,4), (4,2), (2,5), (5,0), (6,3), (5,6),
               (7,8), (8,8), (8,9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16), (16, 17)])
    print(g)
    g.to_undirected()
    print(g)
    print(len(g.decompose()))
    print(g.decompose()[0])
    print(g.decompose()[1])
    g = g.decompose(maxcompno=1)[0]
    g.simplify()
    print(g)


def cmdscale(g: Graph, profile: dict):
    '''cmdscale: http://www.nervouscomputer.com/hfs/cmdscale-in-python/'''

    graph_dir = PurePath(profile['root']).joinpath(profile['name'])
    Λ_path, E_path = Path(graph_dir.joinpath('eigenvalues')), Path(graph_dir.joinpath('eigenvectors'))
    if not profile['force'] and Λ_path.exists() and E_path.exists():
        return io_array(Λ_path), io_array(E_path)

    # Distance matrix (All-pairs shortest path length in numpy array)
    distance_file = graph_dir.joinpath('graph', 'distance')
    try:
        if profile['force']: raise FileNotFoundError
        d = io_array(distance_file)
    except FileNotFoundError:
        paths = g.shortest_paths(weights=None)
        d = np.array(paths, dtype=np.int)
        io_array(str(distance_file), d)
        if _DEBUG_ and g.number_of_nodes() < 100: print(d)
        benchmark(message='All-pairs shortest path length over the graph')

    # Classical Multi Dimensional Scaling
    N, _ = d.shape
    J = np.eye(N) - np.ones((N, N)) / N      # Centering matrix
    B = - J.dot(d * d).dot(J) / 2.0          # Apply double centering
    Λ, E = np.linalg.eigh(B)

    Λ_positive = Λ > 0                       # Choose positive eigenvalues
    Λ, E = Λ[Λ_positive], E[:, Λ_positive]
    Λ_descending = np.argsort(-Λ)            # Organize in descending order of eigenvalues
    Λ, E = Λ[Λ_descending], E[:, Λ_descending]
    dim_hd = Λ.shape[0]
    layout_hd = E.dot(np.diag(np.sqrt(Λ)))
    profile['dim_hd'] = layout_hd.shape

    if _DEBUG_:
        for i in range(dim_hd):
            v = E[:, i]
            diff = B.dot(v) - Λ[i] * v
            print(diff.dot(diff))
            assert diff.dot(diff) < 1e-10 # Confirm that E are truely eigenvectors

    L = np.eye(N, dim_hd).dot(np.diag(Λ))

    layout_dir = graph_dir.joinpath('layout')
    io_array(layout_dir.joinpath('eigenvalues'),  Λ)
    io_array(layout_dir.joinpath('eigenvectors'), E)
    io_array(layout_dir.joinpath('layout_hd'),    layout_hd)

    benchmark(message='Classical multi dimensional scaling')

    return Λ, E


def centrality(g: Graph, profile: dict):

    directory = None
    def save(name: str, c: np.array):
        io_array(directory.joinpath(name), c)
        benchmark(message='{0}.{1}'.format(directory, name))

    directory = PurePath(profile['root']).joinpath(profile['name'], 'centrality', 'v')
    save('betweenness', g.betweenness(directed=False))
    save('closeness', g.closeness())
    save('clustering', g.transitivity_local_undirected(mode='zero'))
    save('degree', g.degree())
    save('eigenvector', g.eigenvector_centrality(directed=False))
    save('hits_hub', g.hub_score()) # The Hub score for Kleinberg's HITS model
    save('pagerank', g.pagerank(directed=False))

    # Personalized PageRank score
    #save('ppagerank', g.personalized_pagerank(*args))


    directory = PurePath(profile['root']).joinpath(profile['name'], 'centrality', 'e')
    save('betweenness', g.edge_betweenness(directed=False))


def analyse(root: PurePath, path: PurePath, profile: dict) -> Graph:
    g = normalize(read(path), profile)

    dataset_dir = root.joinpath(profile['name'])

    Λ, E = cmdscale(g, profile)
    centrality(g, profile)

    pickle(root.joinpath(profile['name'], 'misc', 'profile.p'), profile)
    print(json.dumps(profile, indent = 4))

    return g


if __name__ == '__main__':
    profile = dict(force=True,
                   root='/Users/wakita/Dropbox (smartnova)/work/glvis/data/dataset')

    dataset = '/Users/wakita/Dropbox (smartnova)/work/glvis/data/takami-svf/'
    testcase = {
        'hypercube-4d': dataset + 'graphs/hypercube-4d.graphml',
        'lesmis': dataset + 'lesmis.gml',
        'math': dataset + 'math.wikipedia/math.graphml',
        'gdea_conf': dataset + 'gdea_conf_paper_1995_2011.gml'
    }

    for name, path in testcase.items():
        #g = normalize(read(PurePath(path)), dict(profile, name=name))
        g = analyse(PurePath(profile['root']), PurePath(path), dict(profile, name=name))
        if all([len(label) > 0 for label in g.vs['label']]):
            print(g.vs['label'][0:4])
        else: print('No labels')
