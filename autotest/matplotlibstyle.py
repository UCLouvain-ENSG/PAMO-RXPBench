

graph_legend_params = {
    "fancybox":0,
    "framealpha":1.0,
    "frameon":False,
    #"fontsize": 15,
    "loc" :'upper right',
    # "title_fontsize": 15,
}

# to be used with plot-bar3.py graph
bar_graph_legend_params = graph_legend_params.copy()
bar_graph_legend_params.update({
    "bbox_to_anchor": (0.5, 1.55),
    "ncol": 2,
    "loc": 'upper center'
    })

graph_tick_params = {
    "direction":"in",
    "which":"both",
    "axis":"both",
    "grid_linestyle":"dotted",
    "grid_color":"#444444",
    "bottom": True,
    "top": True,
    "left": True,
    "right": True,
}

