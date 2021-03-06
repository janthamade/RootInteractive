from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, ColorBar, HoverTool, CDSView, GroupFilter, VBar, HBar, Quad, Image
from bokeh.models.widgets.tables import ScientificFormatter, DataTable
from bokeh.transform import *
from RootInteractive.Tools.aliTreePlayer import *
# from bokehTools import *
from bokeh.layouts import *
from bokeh.palettes import *
from bokeh.io import push_notebook
import logging
import pyparsing
from IPython import get_ipython
from bokeh.models.widgets import *
from bokeh.models import CustomJS, ColumnDataSource
from RootInteractive.Tools.pandaTools import *
from RootInteractive.InteractiveDrawing.bokeh.bokehVisJS3DGraph import BokehVisJSGraph3D
from RootInteractive.InteractiveDrawing.bokeh.HistogramCDS import HistogramCDS
from RootInteractive.InteractiveDrawing.bokeh.Histo2dCDS import Histo2dCDS
import copy
from RootInteractive.Tools.compressArray import *
from RootInteractive.InteractiveDrawing.bokeh.CDSCompress import CDSCompress
from RootInteractive.InteractiveDrawing.bokeh.HistoStatsCDS import HistoStatsCDS
# tuple of Bokeh markers
bokehMarkers = ["square", "circle", "triangle", "diamond", "squarecross", "circlecross", "diamondcross", "cross",
                "dash", "hex", "invertedtriangle", "asterisk", "squareX", "X"]

# default tooltips for 1D and 2D histograms
defaultHistoTooltips = [
    ("range", "[@{bin_left}, @{bin_right}]"),
    ("count", "@bin_count")
]

defaultHisto2DTooltips = [
    ("range X", "[@{bin_left}, @{bin_right}]"),
    ("range Y", "[@{bin_bottom}, @{bin_top}]"),
    ("count", "@bin_count")
]

def makeJScallbackOptimized(widgetDict, cdsOrig, cdsSel, **kwargs):
    options = {
        "verbose": 0,
        "nPointRender": 10000,
        "cmapDict": None,
        "histogramList": []
    }
    options.update(kwargs)

    code = \
        """
    const t0 = performance.now();
    const dataOrig = cdsOrig.data;
    let dataSel = null;
    if(cdsSel != null){
        dataSel = cdsSel.data;
        console.log('%f\t%f\t',dataOrig.index.length, dataSel.index.length);
    }
    const nPointRender = options.nPointRender;
    let nSelected=0;
    for (const i in dataSel){
        dataSel[i] = [];
    }
    const precision = 0.000001;
    const size = dataOrig.index.length;
    let isSelected = new Array(size);
    for(let i=0; i<size; ++i){
        isSelected[i] = true;
    }
    let permutationFilter = [];
    let indicesAll = [];
    for (const key in widgetDict){
        const widget = widgetDict[key];
        const widgetType = widget.type;
        if(widgetType == "Slider"){
            const col = dataOrig[key];
            const widgetValue = widget.value;
            const widgetStep = widget.step;
            for(let i=0; i<size; i++){
                isSelected[i] &= (col[i] >= widgetValue-0.5*widgetStep);
                isSelected[i] &= (col[i] <= widgetValue+0.5*widgetStep);
            }
        }
        if(widgetType == "RangeSlider"){
            const col = dataOrig[key];
            const low = widget.value[0];
            const high = widget.value[1];
            for(let i=0; i<size; i++){
                isSelected[i] &= (col[i] >= low);
                isSelected[i] &= (col[i] <= high);
            }
        }
        if(widgetType == "Select"){
            const col = dataOrig[key];
            let widgetValue = widget.value;
            widgetValue = widgetValue === "True" ? true : widgetValue;
            widgetValue = widgetValue === "False" ? false : widgetValue;
            for(let i=0; i<size; i++){
                let isOK = Math.abs(col[i] - widgetValue) <= widgetValue * precision;
                isOK|=(col[i] == widgetValue)
                isSelected[i] &= (col[i] == widgetValue) | isOK;
            }
        }
        if(widgetType == "MultiSelect"){
            const col = dataOrig[key];
            const widgetValue = widget.value.map((val)=>{
                if(val === "True") return true;
                if(val === "False") return false;
                if(!isNaN(val)) return Number(val);
                return val;
            });
            for(let i=0; i<size; i++){
                let isOK = widgetValue.reduce((acc,cur)=>acc|Math.abs(cur-col[i])<precision,0);
                if (!isOK){
                    isOK = widgetValue.reduce((acc,cur)=>acc|cur===col[i],0);
                }
                isSelected[i] &= isOK;
            }
        }
        if(widgetType == "CheckboxGroup"){
            const col = dataOrig[key];
            const widgetValue = widget.value;
            for(let i=0; i<size; i++){
                isOK = Math.abs(col[i] - widgetValue) <= widgetValue * precision;
                isSelected &= (col[i] == widgetValue) | isOK;
            }
        }
        // This is broken, to be fixed later.
/*        if(widgetType == "TextInput"){
            const widgetValue = widget.value;
             if (queryText.length > 1)  {
                let queryString='';
                let varString='';
                eval(varString+ 'var result = ('+ queryText+')');
                for(let i=0; i<size; i++){
                    isSelected[i] &= result[i];
                }
             }
        }*/
    }
    if(nPointRender > 0 && cdsSel != null){
        for (let i = 0; i < size; i++){
        let randomIndex = 0;
            if (isSelected[i]){
                if(nSelected < nPointRender){
                    permutationFilter.push(i);
                } else if(Math.random() < nPointRender / (nSelected+1)) {
                    randomIndex = Math.floor(Math.random()*nPointRender)|0;
                    permutationFilter[randomIndex] = i;
                }
                nSelected++;
            }
        }
        nSelected = Math.min(nSelected, nPointRender);
        for (const key in dataSel){
            const colSel = dataSel[key];
            const colOrig = dataOrig[key];
            for(let i=0; i<nSelected; i++){
                colSel[i] = colOrig[permutationFilter[i]];
            }
        }
    }
    const t1 = performance.now();
    console.log(`Filtering took ${t1 - t0} milliseconds.`);
    const view = options.view;
    const histogramList = options.histogramList
    if(histogramList != []){
        for (let i = 0; i < size; i++){
            if (isSelected[i]){
                indicesAll.push(i);
            }
        }
        for (const histo of histogramList){
            histo.view = indicesAll;
            histo.update_range();
        }
    }
    const t2 = performance.now();
    console.log(`Histogramming took ${t2 - t1} milliseconds.`);
    const cmapDict = options.cmapDict;
    if (cmapDict !== undefined){
        for(const key in cmapDict){
            const cmapList = cmapDict[key];
            for(let i=0; i<cmapList.length; i++){
                const col = cmapList[i][0].data[key];
                if(col.length === 0) continue;
                const low = col.reduce((acc, cur)=>Math.min(acc,cur),col[0]);
                const high = col.reduce((acc, cur)=>Math.max(acc,cur),col[0]);
                cmapList[i][1].transform.high = high;
                cmapList[i][1].transform.low = low;
//                    cmapList[i][1].transform.change.emit(); - The previous two lines will emit an event - avoiding bokehjs events might improve the performance
            }
        }
    }
    const t3 = performance.now();
    console.log(`Updating colormaps took ${t3 - t2} milliseconds.`);
    if(nPointRender > 0 && cdsSel != null){
        cdsSel.change.emit();
        const t4 = performance.now();
        console.log(`Updating cds took ${t4 - t3} milliseconds.`);
    }
    if(options.cdsHistoSummary !== null){
        options.cdsHistoSummary.update();
    }
    console.log(\"nSelected:%d\",nSelected);
    """
    if options["verbose"] > 0:
        logging.info("makeJScallback:\n", code)
    # print(code)
    callback = CustomJS(args={'widgetDict': widgetDict, 'cdsOrig': cdsOrig, 'cdsSel': cdsSel, 'options': options},
                        code=code)
    return callback


def __processBokehLayoutRow(layoutRow, figureList, layoutList, optionsMother, verbose=0):
    """
    :param layoutRow:
    :param figureList:
    :param layoutList:
    :param optionsMother:
    :param verbose:
    :return:
    """
    if verbose > 0: logging.info("Raw", layoutRow)
    array = []
    layoutList.append(array)
    option = __processBokehLayoutOption(layoutRow)
    if verbose > 0: logging.info("Option", option)
    for key in optionsMother:
        if not (key in option):
            option[key] = optionsMother[key]
    for idx, y in enumerate(layoutRow):
        if not y.isdigit(): continue
        try:
            fig = figureList[int(y)]
        except:
            logging.error("out of range index", y)
        array.append(fig)
        if type(fig).__name__ == 'DataTable':
            continue
        if 'commonY' in option:
            if option["commonY"] >= 0:
                try:
                    fig.y_range = figureList[int(option["commonY"])].y_range
                except ValueError:
                    logging.info('Failed: to process option ' + option["commonY"])
                    continue
                except AttributeError:
                    logging.info('Failed: to process option ' + option["commonY"])
                    continue
        if 'commonX' in option:
            if option["commonX"] >= 0:
                try:
                    fig.x_range = figureList[int(option["commonX"])].x_range
                except ValueError:
                    if verbose > 0: logging.info('Failed: to process option ' + option["commonX"])
                    continue
                except AttributeError:
                    logging.info('Failed: to process option ')
                    continue

        if (idx > 0) & ('y_visible' in option):
            fig.yaxis.visible = bool(option["y_visible"]==1)
        if (idx == 0) & ('y_visible' in option):
            fig.yaxis.visible = bool(option["y_visible"]!=0)
        if 'x_visible' in option:
            fig.xaxis.visible = bool(option["x_visible"]==1)
    nCols = len(array)
    for fig in array:
        if type(fig).__name__ == 'Figure':
            if 'plot_width' in option:
                fig.plot_width = int(option["plot_width"] / nCols)
            if 'plot_height' in option:
                fig.plot_height = int(option["plot_height"])
        if type(fig).__name__ == 'DataTable':
            if 'plot_width' in option:
                fig.width = int(option["plot_width"] / nCols)
            if 'plot_height' in option:
                fig.height = int(option["plot_height"])
        if type(fig).__name__ == 'BokehVisJSGraph3D':
            if 'plot_width' in option:
                fig.width = int(option["plot_width"] / nCols)
            if 'plot_height' in option:
                fig.height = int(option["plot_height"])


def __processBokehLayoutOption(layoutOptions):
    """
    :param layoutOptions:
    :return:
    """
    # https://stackoverflow.com/questions/9305387/string-of-kwargs-to-kwargs
    options = {}
    for x in layoutOptions:
        if not (type(x) == str): continue
        if "=" in str(x):  # one of the way to see if it's list
            try:
                k, v = x.split("=")
            except ValueError:
                continue
            options[k] = v
            if v.isdigit():
                options[k] = int(v)
            else:
                try:
                    options[k] = float(v)
                except ValueError:
                    options[k] = v
    return options


def processBokehLayoutArray(widgetLayoutDesc, widgetArray):
    """
    apply layout on plain array of bokeh figures, resp. interactive widgets
    :param widgetLayoutDesc: array desciption of layout
    :param widgetArray: input plain array of widgets/figures
    :return: combined figure
    Example:  in tutorial/bokehDraw/makePandaWidgets.ipynb
    widgetLayoutDesc=[
        [0,1,2],
        [3,4,5],
        [6,7],
        {'width':10,'sizing_mode':'scale_width'}
    ]
    figureLayoutDesc=[
        [0,1,2, {'commonX':1,'y_visible':2, 'plot_height':300}],
        [2, {'commonX':1, 'y_visible':0}],
        {'width':10,'plot_height':200, 'sizing_mode':'scale_width'}
    ]
    """
    options = {
        'commonX': -1, 'commonY': -1,
        'x_visible': 1, 'y_visible': 1,
        'plot_width': -1, 'plot_height': -1,
        'sizing_mode': 'scale_width',
        'legend_visible': True
    }

    widgetRows = []
    nRows = len(widgetArray)
    # get/apply global options if exist
    if isinstance(widgetLayoutDesc[-1], dict):
        nRows -= 1
        options.update(widgetLayoutDesc[-1])
        widgetLayoutDesc = widgetLayoutDesc[0:-1]

    for rowWidget in widgetLayoutDesc:
        rowOptions = {}
        rowOptions.update(options)
        # patch local option
        if isinstance(rowWidget[-1], dict):
            rowOptions.update(rowWidget[-1])
            rowWidget = rowWidget[0:-1]
        rowWidgetArray0 = []
        for i, iWidget in enumerate(rowWidget):
            figure = widgetArray[iWidget]
            rowWidgetArray0.append(figure)
            if hasattr(figure, 'x_range'):
                if rowOptions['commonX'] >= 0:
                    figure.x_range = widgetArray[int(rowOptions["commonX"])].x_range
                if rowOptions['commonY'] >= 0:
                    figure.y_range = widgetArray[int(rowOptions["commonY"])].y_range
                if rowOptions['x_visible'] == 0:
                    figure.xaxis.visible = False
                else:
                     figure.xaxis.visible = True
                #figure.xaxis.visible = bool(rowOptions["x_visible"])
                if rowOptions['y_visible'] == 0:
                    figure.yaxis.visible = False
                if rowOptions['y_visible'] == 2:
                    if i > 0: figure.yaxis.visible = False
            if hasattr(figure, 'plot_width'):
                if rowOptions["plot_width"] > 0:
                    plot_width = int(rowOptions["plot_width"] / len(rowWidget))
                    figure.plot_width = plot_width
                if rowOptions["plot_height"] > 0:
                    figure.plot_height = rowOptions["plot_height"]
                figure.legend.visible = rowOptions["legend_visible"]
            if type(figure).__name__ == "DataTable":
                figure.height = int(rowOptions["plot_height"])
            if type(figure).__name__ == "BokehVisJSGraph3D":
                if rowOptions["plot_width"] > 0:
                    plot_width = int(rowOptions["plot_width"] / len(rowWidget))
                    figure.width = plot_width
                if rowOptions["plot_height"] > 0:
                    figure.height = rowOptions["plot_height"]

        rowWidgetArray = row(rowWidgetArray0, sizing_mode=rowOptions['sizing_mode'])
        widgetRows.append(rowWidgetArray)
    return column(widgetRows, sizing_mode=options['sizing_mode'])


def gridplotRow(figList0, **options):
    """
    Make gridplot -resizing properly rows

    :param figList0: input array of figures
    :param options:
    :return:
    """
    figList = []
    for frow in figList0:
        figList.append([row(frow)])
    pAll = gridplot(figList, **options)
    return pAll


def makeBokehDataTable(dataFrame, source, include, exclude, **kwargs):
    """
    Create widget for datatable

    :param dataFrame:
    input data frame
    :param source:
    :return:
    """
    columns = []
    for col in dataFrame.columns.values:
        isOK = True
        if hasattr(dataFrame, "meta"):
            title = dataFrame.meta.metaData.get(col + ".OrigName", col);
        else:
            title = col
        if include:
            isOK = False
            if re.match(include, col):
                isOK = True
        if exclude:
            if re.match(exclude, col):
                isOK = False
        if isOK:
            columns.append(TableColumn(field=col, title=title))
    data_table = DataTable(source=source, columns=columns, **kwargs)
    return data_table


def makeBokehHistoTable(histoDict, rowwise=False, **kwargs):
    histo_names = []
    histo_columns = []
    bin_centers = []
    edges_left = []
    edges_right = []
    sources = []
    quantiles = []
    compute_quantile = []
    sum_range = []

    if "formatter" in kwargs:
        formatter = kwargs["formatter"]
    else:
        formatter = ScientificFormatter(precision=3)

    for iHisto in histoDict:
        if histoDict[iHisto]["type"] == "histo2d":
            histo_names.append(histoDict[iHisto]["name"]+"_X")
            histo_columns.append("bin_count")
            bin_centers.append("x")
            edges_left.append("bin_left")
            edges_right.append("bin_right")
            sources.append(histoDict[iHisto]["cds"])
            compute_quantile.append(False)
            histo_names.append(histoDict[iHisto]["name"]+"_Y")
            histo_columns.append("bin_count")
            bin_centers.append("y")
            edges_left.append("bin_bottom")
            edges_right.append("bin_top")
            sources.append(histoDict[iHisto]["cds"])
            compute_quantile.append(False)
        else:
            histo_names.append(histoDict[iHisto]["name"])
            histo_columns.append("bin_count")
            bin_centers.append("bin_center")
            edges_left.append("bin_left")
            edges_right.append("bin_right")
            sources.append(histoDict[iHisto]["cds"])
            compute_quantile.append(True)
            if "quantiles" in histoDict[iHisto]:
                quantiles += histoDict[iHisto]["quantiles"]
            if "sum_range" in histoDict[iHisto]:
                sum_range += histoDict[iHisto]["sum_range"]

    quantiles = [*{*quantiles}]
    sum_range_uniq = []
    for i in sum_range:
        if i not in sum_range_uniq:
            sum_range_uniq.append(i)
    stats_cds = HistoStatsCDS(sources=sources, names=histo_names, bincount_columns=histo_columns, bin_centers=bin_centers,
                              quantiles=quantiles, compute_quantile=compute_quantile, rowwise=rowwise,
                              edges_left=edges_left, edges_right=edges_right, sum_range=sum_range_uniq)
    if rowwise:
        columns = [TableColumn(field="description")]
        for i in histo_names:
            columns.append(TableColumn(field=i, formatter=formatter))
        data_table = DataTable(source=stats_cds, columns=columns, **kwargs)
    else:
        columns = [TableColumn(field="name"), TableColumn(field="mean", formatter=formatter),
                   TableColumn(field="std", formatter=formatter), TableColumn(field="entries", formatter=formatter)]
        for (i, iQuantile) in enumerate(quantiles):
            columns.append(TableColumn(field="quantile_"+format(i), title="Quantile "+format(iQuantile),
                                       formatter=formatter))
        for (i, iBox) in enumerate(sum_range_uniq):
            columns.append(TableColumn(field="sum_"+format(i), title="Σ("+format(iBox[0])+","+format(iBox[1])+")",
                                       formatter=formatter))
            columns.append(TableColumn(field="sum_normed_"+format(i), title="Σ_normed("+format(iBox[0])+","+format(iBox[1])+")",
                                       formatter=formatter))
        data_table = DataTable(source=stats_cds, columns=columns, **kwargs)
    return stats_cds, data_table


def bokehDrawArray(dataFrame, query, figureArray, histogramArray=[], **kwargs):
    """
    Wrapper bokeh draw array of figures

    :param dataFrame:         - input data frame
    :param query:             - query
    :param figureArray:       - figure array
    :param kwargs:
    :return:
        variable list:
            * pAll
            * handle
            * source
            * plotArray

    See example test:
        RootInteractive/InteractiveDrawing/bokeh/test_bokehDrawSA.py
    """
    options = {
        'line': -1,
        'size': 2,
        'tools': 'pan,box_zoom, wheel_zoom,box_select,lasso_select,reset,save',
        'tooltips': [],
        'histoTooltips': defaultHistoTooltips,
        'histo2dTooltips': defaultHisto2DTooltips,
        'y_axis_type': 'auto',
        'x_axis_type': 'auto',
        'plot_width': 600,
        'plot_height': 400,
        'errX': '',
        'errY': '',
        'commonX': 0,
        'commonY': 0,
        'ncols': -1,
        'layout': '',
        'widgetLayout': '',
        'palette': Spectral6,
        "marker": "square",
        "markers": bokehMarkers,
        "color": None,
        "colors": 'Category10',
        "colorZvar": '',
        "rescaleColorMapper": False,
        "filter": '',
        'doDraw': 0,
        "legend_field": None,
        'nPointRender': 10000,
        "nbins": 10,
        "weights": None,
        "histo2d": False,
        "range": None,
        "flip_histogram_axes": False,
        "show_histogram_error": False,
        "arrayCompression": None,
        "removeExtraColumns": True,
    }
    options.update(kwargs)
    if query is not None:
        dfQuery = dataFrame.query(query)
        if hasattr(dataFrame, 'metaData'):
            dfQuery.metaData = dataFrame.metaData
            logging.info(dfQuery.metaData)
    else:
        dfQuery = dataFrame.copy()
    # Check/resp. load derived variables
    i: int
    dfQuery, histogramDict, output_cdsSel, columnNameDict = makeDerivedColumns(dfQuery, figureArray, histogramArray=histogramArray, options=options)

    try:
        cdsFull = ColumnDataSource(dfQuery)
        if output_cdsSel:
            source = ColumnDataSource(dfQuery.sample(min(dfQuery.shape[0], options['nPointRender'])))
        else:
            source = None
    except:
        logging.error("Invalid source:", source)
    # define default options

    plotArray = []
    colorAll = all_palettes[options['colors']]
    colorMapperDict = {}
    cdsHistoSummary = None

    if options['arrayCompression'] is not None:
        print("compressCDSPipe")
        cdsCompress0, sizeMap= compressCDSPipe(dfQuery,options["arrayCompression"],1)
        cdsCompress=CDSCompress(source=None,inputData=cdsCompress0, sizeMap=sizeMap)
        cdsFull=cdsCompress

    histogramDict = bokehMakeHistogramCDS(dfQuery, cdsFull, histogramArray, histogramDict)

    histoList = []
    for i in histogramDict:
        histoList.append(histogramDict[i]["cds"])

    if isinstance(figureArray[-1], dict):
        options.update(figureArray[-1])
    for i, variables in enumerate(figureArray):
        logging.info("%d\t%s", i, variables)
        if isinstance(variables, dict):
            continue
        if variables[0] == 'table':
            TOptions = {
                'include': '',
                'exclude': ''
            }
            if len(variables) > 1:
                TOptions.update(variables[1])
            plotArray.append(makeBokehDataTable(dfQuery, source, TOptions['include'], TOptions['exclude']))
            continue
        if variables[0] == 'tableHisto':
            TOptions = {'rowwise': False}
            if len(variables) > 1:
                TOptions.update(variables[1])
            cdsHistoSummary, tableHisto = makeBokehHistoTable(histogramDict, rowwise=TOptions["rowwise"])
            plotArray.append(tableHisto)
            continue
        xAxisTitle = ""
        yAxisTitle = ""
        # zAxisTitle = ""
        plotTitle = ""
        for varY in variables[1]:
            if hasattr(dfQuery, "meta"):
                yAxisTitle += dfQuery.meta.metaData.get(varY + ".AxisTitle", varY)
            else:
                yAxisTitle += varY
            yAxisTitle += ','
        for varX in variables[0]:
            if hasattr(dfQuery, "meta"):
                xAxisTitle += dfQuery.meta.metaData.get(varX + ".AxisTitle", varX)
            else:
                xAxisTitle += varX
            xAxisTitle += ','
        xAxisTitle = xAxisTitle[:-1]
        yAxisTitle = yAxisTitle[:-1]
        plotTitle += yAxisTitle + " vs " + xAxisTitle

        optionLocal = copy.copy(options)
        if len(variables) > 2:
            logging.info("Option %s", variables[2])
            optionLocal.update(variables[2])
        if 'varZ' in optionLocal.keys():
            dfQuery, varNameY = pandaGetOrMakeColumn(dfQuery, variables[1][0])
            _, varNameX = pandaGetOrMakeColumn(dfQuery, variables[0][0])
            _, varNameZ = pandaGetOrMakeColumn(dfQuery, optionLocal['varZ'])
            _, varNameColor = pandaGetOrMakeColumn(dfQuery, optionLocal['colorZvar'])
            options3D = {"width": "99%", "height": "99%"}
            plotI = BokehVisJSGraph3D(width=options['plot_width'], height=options['plot_height'],
                                      data_source=source, x=varNameX, y=varNameY, z=varNameZ, style=varNameColor,
                                      options3D=options3D)
            plotArray.append(plotI)
            continue
        else:
            figureI = figure(plot_width=options['plot_width'], plot_height=options['plot_height'], title=plotTitle,
                             tools=options['tools'], x_axis_type=options['x_axis_type'],
                             y_axis_type=options['y_axis_type'])

        figureI.xaxis.axis_label = xAxisTitle
        figureI.yaxis.axis_label = yAxisTitle

        # graphArray=drawGraphArray(df, variables)
        lengthX = len(variables[0])
        lengthY = len(variables[1])
        length = max(len(variables[0]), len(variables[1]))
        color_bar = None
        mapperC = None
        if (len(optionLocal["colorZvar"]) > 0):
            logging.info("%s", optionLocal["colorZvar"])
            varColor = optionLocal["colorZvar"]
            mapperC = linear_cmap(field_name=varColor, palette=optionLocal['palette'], low=min(dfQuery[varColor]),
                                  high=max(dfQuery[varColor]))
            if optionLocal["rescaleColorMapper"]:
                if optionLocal["colorZvar"] in colorMapperDict:
                    colorMapperDict[optionLocal["colorZvar"]] += [[source, mapperC]]
                else:
                    colorMapperDict[optionLocal["colorZvar"]] = [[source, mapperC]]
            color_bar = ColorBar(color_mapper=mapperC['transform'], width=8, location=(0, 0), title=varColor)

        defaultHoverToolRenderers = []

        for i in range(0, length):
            dfQuery, varNameX = pandaGetOrMakeColumn(dfQuery, variables[0][i % lengthX])
            if variables[1][i % lengthY] in histogramDict:
                iHisto = histogramDict[variables[1][i % lengthY]]
                if iHisto["type"] == "histogram":
                    dfQuery, varNameY = pandaGetOrMakeColumn(dfQuery, iHisto["variables"][0])
                elif iHisto["type"] == "histo2d":
                    dfQuery, varNameX = pandaGetOrMakeColumn(dfQuery, iHisto["variables"][0])
                    dfQuery, varNameY = pandaGetOrMakeColumn(dfQuery, iHisto["variables"][1])
            else:
                dfQuery, varNameY = pandaGetOrMakeColumn(dfQuery, variables[1][i % lengthY])
            if mapperC is not None:
                color = mapperC
            else:
                color = colorAll[max(length, 4)][i]
            if optionLocal['color'] is not None:
                color=optionLocal['color']
            try:
                marker = optionLocal['markers'][i]
            except:
                marker = optionLocal['markers']
            if len(variables) > 2:
                logging.info("Option %s", variables[2])
                optionLocal.update(variables[2])
            varX = variables[0][i % lengthX]
            varY = variables[1][i % lengthY]

            if varY in histogramDict:
                histoHandle = histogramDict[varY]
                if histoHandle["type"] == "histogram":
                    colorHisto = colorAll[max(length, 4)][i]
                    addHistogramGlyph(figureI, histoHandle, marker, colorHisto, optionLocal)
                elif histoHandle["type"] == "histo2d":
                    addHisto2dGlyph(figureI, varNameX, varNameY, histoHandle, colorMapperDict, color, marker, dfQuery,
                                    optionLocal)
            else:
                #                zAxisTitle +=varColor + ","
                #            view = CDSView(source=source, filters=[GroupFilter(column_name=optionLocal['filter'], group=True)])
                drawnGlyph = None
                if optionLocal["legend_field"] is None:
                    drawnGlyph = figureI.scatter(x=varNameX, y=varNameY, fill_alpha=1, source=source, size=optionLocal['size'],
                                color=color, marker=marker, legend_label=varY + " vs " + varX)
                else:
                    drawnGlyph = figureI.scatter(x=varNameX, y=varNameY, fill_alpha=1, source=source, size=optionLocal['size'],
                                color=color, marker=marker, legend_field=optionLocal["legend_field"])
                defaultHoverToolRenderers.append(drawnGlyph)
                if ('errX' in optionLocal.keys()) & (optionLocal['errX'] != ''):
                    errorX = HBar(y=varNameY, height=0, left=varNameX+"_lower", right=varNameX+"_upper", line_color=color)
                    figureI.add_glyph(source, errorX)
                if ('errY' in optionLocal.keys()) & (optionLocal['errY'] != ''):
                    errorY = VBar(x=varNameX, width=0, bottom=varNameY+"_lower", top=varNameY+"_upper", line_color=color)
                    figureI.add_glyph(source, errorY)
                #    errors = Band(base=varNameX, lower=varNameY+"_lower", upper=varNameY+"_upper",source=source)
                #    figureI.add_layout(errors)

        if color_bar != None:
            figureI.add_layout(color_bar, 'right')
        if defaultHoverToolRenderers:
            figureI.add_tools(HoverTool(tooltips=optionLocal["tooltips"], renderers=defaultHoverToolRenderers))
        figureI.legend.click_policy = "hide"
        #        zAxisTitle=zAxisTitle[:-1]
        #        if(len(zAxisTitle)>0):
        #            plotTitle += " Color:" + zAxisTitle
        #        figureI.title = plotTitle
        plotArray.append(figureI)
    if isinstance(options['layout'], list):
        pAll = processBokehLayoutArray(options['layout'], plotArray)
        layoutList = [pAll]
    if options['doDraw'] > 0:
        show(pAll)
    return pAll, source, layoutList, dfQuery, colorMapperDict, cdsFull, histoList, cdsHistoSummary


def addHisto2dGlyph(fig, x, y, histoHandle, colorMapperDict, color, marker, dfQuery, options):
    visualization_type = "heatmap"
    if "visualization_type" in options:
        visualization_type = options["visualization_type"]
    cdsHisto = histoHandle["cds"]

    tooltips = None
    if "tooltips" in histoHandle:
        tooltips = histoHandle["tooltips"]
    elif "tooltips" in options:
        tooltips = options["histo2dTooltips"]

    if visualization_type == "heatmap":
        # Flipping histogram axes probably doesn't make sense in this case.
        mapperC = linear_cmap(field_name="bin_count", palette=options['palette'], low=0,
                              high=1)
        if ("bin_count") in colorMapperDict:
            colorMapperDict["bin_count"] += [[cdsHisto, mapperC]]
        else:
            colorMapperDict["bin_count"] = [[cdsHisto, mapperC]]
        color_bar = ColorBar(color_mapper=mapperC['transform'], width=8, location=(0, 0),
                             title=x + " vs " + y)
        histoGlyph = Quad(left="bin_left", right="bin_right", bottom="bin_bottom", top="bin_top",
                          fill_color=mapperC)
        histoGlyphRenderer = fig.add_glyph(cdsHisto, histoGlyph)
        fig.add_layout(color_bar, 'right')
    elif visualization_type == "colZ":
        mapperC = linear_cmap(field_name="y", palette=options['palette'], low=min(dfQuery[y]),
                                  high=max(dfQuery[y]))
        if "y" in colorMapperDict:
            colorMapperDict["y"] += [[cdsHisto, mapperC]]
        else:
            colorMapperDict["y"] = [[cdsHisto, mapperC]]
        color_bar = ColorBar(color_mapper=mapperC['transform'], width=8, location=(0, 0),
                             title=x + " vs " + y)
        if options["legend_field"] is None:
            histoGlyphRenderer = fig.scatter(x="x", y="bin_count", fill_alpha=1, source=cdsHisto, size=options['size'],
                            color=mapperC, marker=marker, legend_label="Histogram of " + x)
        else:
            histoGlyphRenderer = fig.scatter(x="x", y="bin_count", fill_alpha=1, source=cdsHisto, size=options['size'],
                            color=mapperC, marker=marker, legend_field=options["legend_field"])
        if "show_histogram_error" in options:
            errorbar = VBar(x="x", width=0, top="errorbar_high", bottom="errorbar_low", line_color=mapperC)
            fig.add_glyph(cdsHisto, errorbar)
        fig.add_layout(color_bar, 'right')
    if tooltips is not None:
        fig.add_tools(HoverTool(renderers=[histoGlyphRenderer], tooltips=tooltips))


def addHistogramGlyph(fig, histoHandle, marker, colorHisto, options):
    cdsHisto = histoHandle["cds"]
    if options['color'] is not None:
        colorHisto = options['color']
    tooltips = None
    if "tooltips" in histoHandle:
        tooltips = histoHandle["tooltips"]
    elif "tooltips" in options:
        tooltips = options["histoTooltips"]
    visualization_type = "points"
    histoGlyphRenderer = None
    if "visualization_type" in options:
        visualization_type = options["visualization_type"]
    if visualization_type == "bars":
        if options['flip_histogram_axes']:
            histoGlyph = Quad(left=0, right="bin_count", bottom="bin_left", top="bin_right", fill_color=colorHisto)
        else:
            histoGlyph = Quad(left="bin_left", right="bin_right", bottom=0, top="bin_count", fill_color=colorHisto)
        histoGlyphRenderer = fig.add_glyph(cdsHisto, histoGlyph)
    elif visualization_type == "points":
        if options['flip_histogram_axes']:
            histoGlyphRenderer = fig.scatter(y="bin_center", x="bin_count", color=colorHisto, marker=marker, source=cdsHisto, size=options['size'],
                        legend_label=histoHandle["variables"][0])
            if "show_histogram_error" in options:
                errorbar = HBar(y="bin_center", height=0, left="errorbar_low", right="errorbar_high", line_color=colorHisto)
                fig.add_glyph(cdsHisto, errorbar)
        else:
            histoGlyphRenderer = fig.scatter(x="bin_center", y="bin_count", color=colorHisto, marker=marker, source=cdsHisto, size=options['size'],
                        legend_label=histoHandle["variables"][0])
            if "show_histogram_error" in options:
                errorbar = VBar(x="bin_center", width=0, top="errorbar_high", bottom="errorbar_low", line_color=colorHisto)
                fig.add_glyph(cdsHisto, errorbar)
    if tooltips is not None:
        fig.add_tools(HoverTool(renderers=[histoGlyphRenderer], tooltips=tooltips))

def makeBokehSliderWidget(df, isRange, params, **kwargs):
    options = {
        'type': 'auto',
        'bins': 30,
        'sigma': 4,
        'limits': (0.05, 0.05),
        'title': '',
    }
    options.update(kwargs)
    name = params[0]
    title = params[0]
    if len(options['title']) > 0:
        title = options['title']
    start = 0
    end = 0
    step = 0
    if options['type'] == 'user':
        start = params[1], end = params[2], step = params[3], value = (params[4], params[5])
    elif (options['type'] == 'auto') | (options['type'] == 'minmax'):
        start = df[name].min()
        end = df[name].max()
        step = (end - start) / options['bins']
    elif (options['type'] == 'unique'):
        start = df[name].min()
        end = df[name].max()
        nbins=df[name].unique().size-1
        step = (end - start) / float(nbins)
    elif options['type'] == 'sigma':
        mean = df[name].mean()
        sigma = df[name].std()
        start = mean - options['sigma'] * sigma
        end = mean + options['sigma'] * sigma
        step = (end - start) / options['bins']
    elif options['type'] == 'sigmaMed':
        mean = df[name].median()
        sigma = df[name].std()
        start = mean - options['sigma'] * sigma
        end = mean + options['sigma'] * sigma
        step = (end - start) / options['bins']
    elif options['type'] == 'sigmaTM':
        mean = df[name].trimmed_mean(options['limits'])
        sigma = df[name].trimmed_std(options['limits'])
        start = mean - options['sigma'] * sigma
        end = mean + options['sigma'] * sigma
        step = (end - start) / options['bins']
    if isRange:
        if (start==end):
            start-=1
            end+=1
        value = (start, end)
        slider = RangeSlider(title=title, start=start, end=end, step=step, value=value)
    else:
        value = (start + end) * 0.5
        slider = Slider(title=title, start=start, end=end, step=step, value=value)
    return slider


def makeBokehSelectWidget(df, params, **kwargs):
    options = {'default': 0, 'size': 10}
    options.update(kwargs)
    # optionsPlot = []
    if len(params) == 1:
        optionsPlot = np.sort(df[params[0]].unique()).tolist()
    else:
        optionsPlot = params[1:]
    for i, val in enumerate(optionsPlot):
        optionsPlot[i] = str((val))
    return Select(title=params[0], value=optionsPlot[options['default']], options=optionsPlot)


def makeBokehMultiSelectWidget(df, params, **kwargs):
    # print("makeBokehMultiSelectWidget",params,kwargs)
    options = {'default': 0, 'size': 4}
    options.update(kwargs)
    # optionsPlot = []
    if len(params) == 1:
        try:
            optionsPlot = np.sort(df[params[0]].unique()).tolist()
        except:
            optionsPlot = sorted(df[params[0]].unique().tolist())
    else:
        optionsPlot = params[1:]
    for i, val in enumerate(optionsPlot):
        optionsPlot[i] = str((val))
    # print(optionsPlot)
    return MultiSelect(title=params[0], value=optionsPlot, options=optionsPlot, size=options['size'])


def makeBokehCheckboxWidget(df, params, **kwargs):
    options = {'default': 0, 'size': 10}
    options.update(kwargs)
    # optionsPlot = []
    if len(params) == 1:
        optionsPlot = np.sort(df[params[0]].unique()).tolist()
    else:
        optionsPlot = params[1:]
    for i, val in enumerate(optionsPlot):
        optionsPlot[i] = str(val)
    return CheckboxGroup(labels=optionsPlot, active=[])


def makeBokehWidgets(df, widgetParams, cdsOrig, cdsSel, histogramList=[], cmapDict=None, cdsHistoSummary=None, nPointRender=10000,cdsCompress=None):
    widgetArray = []
    widgetDict = {}
    for widget in widgetParams:
        type = widget[0]
        params = widget[1]
        options = {}
        localWidget = None
        if len(widget) == 3:
            options = widget[2]
        if type == 'range':
            localWidget = makeBokehSliderWidget(df, True, params, **options)
        if type == 'slider':
            localWidget = makeBokehSliderWidget(df, False, params, **options)
        if type == 'select':
            localWidget = makeBokehSelectWidget(df, params, **options)
        if type == 'multiSelect':
            localWidget = makeBokehMultiSelectWidget(df, params, **options)
        # if type=='checkbox':
        #    localWidget=makeBokehCheckboxWidget(df,params,**options)
        if localWidget:
            widgetArray.append(localWidget)
        widgetDict[params[0]] = localWidget
    callback = makeJScallbackOptimized(widgetDict, cdsOrig, cdsSel, histogramList=histogramList, cmapDict=cmapDict, nPointRender=nPointRender, cdsHistoSummary=cdsHistoSummary, cdsCompress=cdsCompress)
    #callback = makeJScallbackOptimized(widgetDict, cdsOrig, cdsSel, histogramList=histogramList, cmapDict=cmapDict, nPointRender=nPointRender)
    for iWidget in widgetArray:
        if isinstance(iWidget, CheckboxGroup):
            iWidget.js_on_click(callback)
        elif isinstance(iWidget, Slider) or isinstance(iWidget, RangeSlider):
            iWidget.js_on_change("value", callback)
        else:
            iWidget.js_on_change("value", callback)
        iWidget.js_on_event("value", callback)
    return widgetArray


def bokehMakeHistogramCDS(dfQuery, cdsFull, histogramArray=[], histogramDict=None, **kwargs):
    options = {"range": None,
               "nbins": 10,
               "weights": None}
    histoDict = {}
    for iHisto in histogramArray:
        sampleVars = iHisto["variables"]
        histoName = iHisto["name"]
        if histogramDict is not None and not histogramDict[histoName]:
            continue
        optionLocal = copy.copy(options)
        optionLocal.update(iHisto)
        if len(sampleVars) == 1:
            _, varNameX = pandaGetOrMakeColumn(dfQuery, sampleVars[0])
            cdsHisto = HistogramCDS(source=cdsFull, nbins=optionLocal["nbins"],
                                    range=optionLocal["range"], sample=varNameX, weights=optionLocal["weights"])
            histoDict[histoName] = iHisto.copy()
            histoDict[histoName].update({"cds": cdsHisto, "type": "histogram"})
        elif len(sampleVars) == 2:
            _, varNameX = pandaGetOrMakeColumn(dfQuery, sampleVars[0])
            _, varNameY = pandaGetOrMakeColumn(dfQuery, sampleVars[1])
            cdsHisto = Histo2dCDS(source=cdsFull, nbins=optionLocal["nbins"],
                                    range=optionLocal["range"], sample_x=varNameX, sample_y=varNameY, weights=optionLocal["weights"])
            histoDict[histoName] = {"cds": cdsHisto, "type": "histo2d", "name": histoName,
                                    "variables": sampleVars}
    return histoDict


def makeDerivedColumns(dfQuery, figureArray=None, histogramArray=None, widgetArray=None, options={}):
    histogramDict = {}
    columnNameDict = {}
    output_cdsSel = False
    if histogramArray is not None:
        for i, histo in enumerate(histogramArray):
            histogramDict[histo["name"]] = False

    if figureArray is not None:
        for i, variables in enumerate(figureArray):
            if len(variables) > 1 and variables[0] != "table" and variables[0] != "tableHisto":
                lengthX = len(variables[0])
                lengthY = len(variables[1])
                length = max(len(variables[0]), len(variables[1]))
                if len(variables) > 2:
                    optionLocal = options.copy()
                    optionLocal.update(variables[2])
                else:
                    optionLocal = options
                for j in range(0, length):
                    if variables[1][j % lengthY] not in histogramDict:
                        output_cdsSel = True
                        dfQuery, varNameX = pandaGetOrMakeColumn(dfQuery, variables[0][j % lengthX])
                        columnNameDict[varNameX] = True
                        dfQuery, varNameY = pandaGetOrMakeColumn(dfQuery, variables[1][j % lengthY])
                        columnNameDict[varNameY] = True
                        if ('errY' in optionLocal) and (optionLocal['errY'] != ''):
                            dfQuery, varNameErrY = pandaGetOrMakeColumn(dfQuery, optionLocal['errY'])
                            seriesErrY = dfQuery[varNameErrY]
                            columnNameDict[varNameErrY] = True
                            if varNameY+'_lower' not in dfQuery.columns:
                                seriesLower = dfQuery[varNameY]-seriesErrY
                                dfQuery[varNameY+'_lower'] = seriesLower
                                columnNameDict[varNameY+'_lower'] = True
                            if varNameY+'_upper' not in dfQuery.columns:
                                seriesUpper = dfQuery[varNameY]+seriesErrY
                                dfQuery[varNameY+'_upper'] = seriesUpper
                                columnNameDict[varNameY+'_upper'] = True
                        if ('errX' in optionLocal) and (optionLocal['errX'] != ''):
                            dfQuery, varNameErrX = pandaGetOrMakeColumn(dfQuery, optionLocal['errX'])
                            seriesErrX = dfQuery[varNameErrX]
                            columnNameDict[varNameErrX] = True
                            if varNameX+'_lower' not in dfQuery.columns:
                                seriesLower = dfQuery[varNameX]-seriesErrX
                                dfQuery[varNameX+'_lower'] = seriesLower
                                columnNameDict[varNameX+'_lower'] = True
                            if varNameX+'_upper' not in dfQuery.columns:
                                seriesUpper = dfQuery[varNameX]+seriesErrX
                                dfQuery[varNameX+'_upper'] = seriesUpper
                                columnNameDict[varNameX+'_upper'] = True
                    else:
                        histogramDict[variables[1][j % lengthY]] = True

    if histogramArray is not None:
        for i, histo in enumerate(histogramArray):
            if histogramDict[histo["name"]]:
                for j, variable in enumerate(histo["variables"]):
                    dfQuery, varName = pandaGetOrMakeColumn(dfQuery, variable)
                    columnNameDict[varName] = True
                if "weights" in histo:
                    dfQuery, varName = pandaGetOrMakeColumn(dfQuery, histo["weights"])
                    columnNameDict[varName] = True

    if widgetArray is not None:
        for iWidget in widgetArray:
            dfQuery, varNameX = pandaGetOrMakeColumn(dfQuery, iWidget[1][0])
            columnNameDict[varNameX] = True

    if "removeExtraColumns" in options and options["removeExtraColumns"]:
        dfQuery = dfQuery[columnNameDict]

    return dfQuery, histogramDict, output_cdsSel, columnNameDict
