from pathlib import PurePath, Path
from glob import glob
import pickle
import sys

import networkx as nx
import numpy as np

_DEBUG_ = True

_extensions = 'adjlist, multiline_adjlist, edgelist, gexf, gml, graph6, graphml, leda, pajek, shp, yaml'.split(', ')

_reader = dict(zip(_extensions,
                   [eval('nx.read_' + type) for type in _extensions]))

##
# Todo
# SparseGraph6 => graph6, GIS Shapefile => shp
# D3-style .json?


def read(path, *args, format=None, **keywords):
    p = PurePath(path)
    stem, suffix = p.stem, p.suffix
    if format is None and suffix[1:] in _reader.keys(): format = suffix[1:]
    if format in _reader.keys():
        try:
            if format == 'gml':
                keywords['label'] = 'id'
            elif format == 'graphml':
                keywords['node_type'] = int
            return _reader[format](path, *args, **keywords)
        except:
            print('Parsing failure')
            e, message, trace = sys.exc_info()
            print(message)
            return None


centrality = dict(
    v=dict(
        degree=nx.degree_centrality,
        closeness=nx.closeness_centrality,
        betweenness=nx.betweenness_centrality,
        eigenverctor=nx.eigenvector_centrality,
        katz=nx.katz_centrality),

    e=dict(
        betweenness=nx.edge_betweenness_centrality))


def compute_graph(G, profile):
    original_nodes = G.nodes()

    root = profile['root']
    dataset = root.joinpath(profile['name'])
    Path(dataset).mkdir(exist_ok=True)

    graph_dir = dataset.joinpath('graph')
    Path(graph_dir).mkdir(exist_ok=True)

    graph_path = graph_dir.joinpath('graph.adjlist')
    if Path(graph_path).is_file():
        G = nx.read_adjlist(str(graph_path))
    else:
        # Remove self loops (if any)
        self_referencing = G.nodes_with_selfloops()
        G.remove_edges_from(zip(self_referencing, self_referencing))
        assert G.number_of_selfloops() == 0

        # Convert to undirected graph (if necessary)
        if nx.is_directed(G): G = G.to_undirected()

        # Find the largest connected component
        G = max(nx.connected_component_subgraphs(G), key=len)

        # Do we need to convert node labels to integers?
        # G = nx.convert_node_labels_to_integers(G)

        nx.write_adjlist(G, str(graph_path))

    # Relabel the node labels
    labels_path = graph_dir.joinpath('labels.p')
    if Path(labels_path).exists():
        with open(str(labels_path), 'rb') as r:
            labels = pickle.load(r)
    elif Path(labels_path).exists():
        labels = labels_path.read_text(encoding='utf8')
        relabel = dict(zip(original_nodes, range(0, G.number_of_nodes())))
        rev_label = dict(zip([(v, k) for k, v in relabel]))
        labels = [labels[rev_label[i]] for i in G.nodes()]
        with open(str(labels_path), 'wb') as w:
            pickle.dump(labels, w)

    profile['#nodes'] = len(G.nodes())
    profile['#edges'] = len(G.edges())

    return G


def CMDS(G, profile):
    graph_dir = profile['root'].joinpath(profile['name'])
    Λ_path, E_path = Path(graph_dir.joinpath('eigenvalues')), Path(graph_dir.joinpath('eigenvectors'))
    if Λ_path.exists() and E_path.exists():
        return np.load(Λ_path), np.load(E_path)

    # Distance matrix (All-pairs shortest path length in numpy array)
    distance_file = graph_dir.joinpath('graph', 'distance.npy')
    if Path(distance_file).is_file():
        D = np.load(str(distance_file))
    else:
        D = np.array([list(row.values()) for row in nx.all_pairs_shortest_path_length(G).values()], dtype=np.int)
        np.save(str(distance_file), D)
        if _DEBUG_ and G.number_of_nodes() < 100: print(D)

    # Classical Multi Dimensional Scaling
    N, _ = D.shape
    J = np.eye(N) - np.ones((N, N)) / N      # Centering matrix
    B = - J.dot(D * D).dot(J) / 2.0          # Apply double centering
    Λ, E = np.linalg.eigh(B)

    Λ_positive = Λ > 0                      # Choose positive eigenvalues
    Λ, E = Λ[Λ_positive], E[:, Λ_positive]
    Λ_descending = np.argsort(-Λ)              # Organize in descending order of eigenvalues
    Λ, E = Λ[Λ_descending], E[:, Λ_descending]
    dim_hd = Λ.shape[0]
    profile['dim_hd'] = dim_hd

    if _DEBUG_:
        for i in range(dim_hd):
            v = E[:, i]
            diff = B.dot(v) - Λ[i] * v
            print(diff.dot(diff))
            assert diff.dot(diff) < 1e-10 # Confirm that E are truely eigenvectors

    L = np.eye(N, dim_hd).dot(np.diag(Λ))

    layout_dir = graph_dir.joinpath('layout')
    Path(layout_dir).mkdir(exist_ok=True)
    np.save(str(layout_dir.joinpath('eigenvalues')),  Λ)
    np.save(str(layout_dir.joinpath('eigenvectors')), E)
    np.save(str(layout_dir.joinpath('layout_hd')), B.dot(L))

    return Λ, E


def convert(root, path):
        G = read(path)
        p = Path(PurePath(path))
        profile = dict(root=root, dir=p.parent, name=p.stem)

        G = compute_graph(G, profile)
        Λ, E = CMDS(G, profile)
        return G, Λ, E

if __name__ == '__main__':
    root = PurePath('/Users/wakita/Dropbox (smartnova)/work/glvis/data/dataset')
    path = '/Users/wakita/Dropbox (smartnova)/work/glvis/data/takami-svf/dolphins.gml'
    G, Λ, E = convert(root, path)

    #nx_draw(G, Λ, E)

if __name__ == '__main__' and False:
    for path in glob('/Users/wakita/Dropbox (smartnova)/work/glvis/data/takami-svf/**/*', recursive=True):
        g = read(path)
        if g: print(path, g.order())