{
    "name": "UDES Hierarchical Tree View",
    "description": """
         Adds a new view type using OWL framework to show a hierarchical view of records on a model.
    """,
    "author": "Unipart Digital",
    "website": "http://github/unipartdigital/udes-open",
    "category": "Tools",
    "version": "0.1",
    "depends": ["base", "web"],
    "qweb": [
        "static/src/components/tree_item/TreeItem.xml",
        "static/src/xml/hierarchical_tree_view.xml",
    ],
    "data": [
        "views/assets.xml",
    ],
}
