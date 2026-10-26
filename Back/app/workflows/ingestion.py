"""Transient graph state; durable jobs and fencing remain in PostgreSQL.

No database sessions, credentials or external clients are put into graph state.
The parse -> persist transaction and the separate versioned index task are the
durable boundaries. This graph deliberately has no in-memory checkpointer that
could be mistaken for recovery across process restarts.
"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.integrations.parser import ParsedDocument


class ImportState(TypedDict, total=False):
    task_id: str
    generation: int
    proceed: bool
    file_name: str
    object_key: str
    parsed: ParsedDocument
    unit_id: str


class IndexState(TypedDict, total=False):
    task_id: str
    generation: int
    proceed: bool
    unit_id: str
    version: int
    operation: str
    texts: list[str]
    records: list[dict]
    vectors: list[list[float]]


def import_graph(load, parse, analyze, persist):
    graph = StateGraph(ImportState)
    graph.add_node('load_document', load)
    graph.add_node('parse_document', parse)
    graph.add_node('analyze_images', analyze)
    graph.add_node('persist_document', persist)
    graph.add_edge(START, 'load_document')
    graph.add_conditional_edges('load_document', lambda s: 'parse' if s['proceed'] else 'end',
                                {'parse': 'parse_document', 'end': END})
    graph.add_conditional_edges('parse_document', lambda s: 'analyze' if s['proceed'] else 'end',
                                {'analyze': 'analyze_images', 'end': END})
    graph.add_conditional_edges('analyze_images', lambda s: 'persist' if s['proceed'] else 'end',
                                {'persist': 'persist_document', 'end': END})
    graph.add_edge('persist_document', END)
    return graph.compile(name='document_import')


def index_graph(load, embed, write, finish):
    graph = StateGraph(IndexState)
    graph.add_node('load_chunks', load)
    graph.add_node('embed_chunks', embed)
    graph.add_node('write_vectors', write)
    graph.add_node('finish_index', finish)
    graph.add_edge(START, 'load_chunks')
    graph.add_conditional_edges('load_chunks',
        lambda s: 'end' if not s['proceed'] else 'delete' if s['operation'] == 'delete' else 'embed',
        {'end': END, 'delete': 'write_vectors', 'embed': 'embed_chunks'})
    graph.add_edge('embed_chunks', 'write_vectors')
    graph.add_conditional_edges('write_vectors', lambda s: 'finish' if s['proceed'] else 'end',
                                {'finish': 'finish_index', 'end': END})
    graph.add_edge('finish_index', END)
    return graph.compile(name='document_index')
