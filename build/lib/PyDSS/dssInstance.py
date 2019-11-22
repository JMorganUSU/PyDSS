from PyDSS.ResultContainer import ResultContainer as RC
from PyDSS.pyContrReader import pyContrReader as pcr
from PyDSS.pyPlotReader import pyPlotReader as ppr
from PyDSS.dssElement import dssElement
from PyDSS.dssCircuit import dssCircuit
from PyDSS.NetworkModifier import Modifier
from PyDSS.dssBus import dssBus
from PyDSS import SolveMode
from PyDSS import pyLogger
import pyControllers
import PyPlots

from opendssdirect.utils import run_command
import opendssdirect as dss
import time
import logging
import os

CONTROLLER_PRIORITIES = 3

DSS_DEFAULTS = {
    # Logging Defaults
    'Logging Level': logging.INFO,
    'Log to external file': True,
    'Display on screen': True,
    'Clear old log files': False,

    # Simulation Options
    'Start Day': 0,
    'End Day': 1,
    'Step resolution (min)': 15,
    'Max Control Iterations': 10,
	'Project Path'   : r'C:\Users\alatif\Desktop\PyDSS-Projects',
    'Simulation Type': 'Daily',
    'Active Project': 'Mikilua',
    'Active Scenario': 'None-None',
    'DSS File': 'MasterCircuit_Mikilua_baseline2.dss',
    'Error tolerance': 1,

    # Results Options
    'Log Results': True,
    'Export Mode': 'byClass',
    'Export Style': 'Single file',

    # Plot Options
    'Network layout': False,
    'Time series': False,
    'XY plot': False,
    'Sag plot': False,
    'Histogram': False,
    'GIS overlay': False,
}


class OpenDSS:
    __TempResultList = []
    __dssInstance = dss
    __dssBuses = {}
    __dssObjects = {}
    __dssObjectsByClass = {}
    __DelFlag = 0
    __pyPlotObjects = {}
    BokehSessionID = None

    def __init__(self, **kwargs):
        DSS_DEFAULTS.update(kwargs)
        kwargs = DSS_DEFAULTS
        rootPath = kwargs['Project Path']
        importPath = os.path.join(rootPath, kwargs['Active Project'], 'PyDSS Scenarios')
        self.__dssPath = {
            'root': rootPath,
            'Import': importPath,
            'pyPlots': os.path.join(importPath, kwargs['Active Scenario'], 'pyPlotList'),
            'ExportLists': os.path.join(importPath, kwargs['Active Scenario'], 'ExportLists'),
            'pyControllers': os.path.join(importPath, kwargs['Active Scenario'], 'pyControllerList'),
            'Export': os.path.join(rootPath, kwargs['Active Project'], 'Exports'),
            'Log': os.path.join(rootPath, kwargs['Active Project'], 'Logs'),
            'dssFiles': os.path.join(rootPath, kwargs['Active Project'], 'DSSfiles'),
        }

        LoggerTag = kwargs['Active Project'] + '_' + kwargs['Active Scenario']
        self.__Logger = pyLogger.getLogger(LoggerTag, self.__dssPath['Log'], LoggerOptions=kwargs)
        self.__Logger.info('An instance of OpenDSS version ' + dss.__version__ + ' has been created.')

        self.__Options = kwargs
        self.__dssFilePath = os.path.join(self.__dssPath['dssFiles'], kwargs['DSS File'])

        self.__dssInstance.Basic.ClearAll()
        self.__dssInstance.utils.run_command('Log=NO')
        run_command('Clear')
        run_command('compile ' + self.__dssFilePath)

        self.__dssCircuit = dss.Circuit
        self.__dssElement = dss.Element
        self.__dssBus = dss.Bus
        self.__dssClass = dss.ActiveClass
        self.__dssCommand = run_command
        self.__dssSolution = dss.Solution
        self.__dssSolver = SolveMode.GetSolver(SimulationSettings=kwargs, dssInstance=self.__dssInstance)

        self.__Modifier = Modifier(dss, run_command, self.__Options)
        #self.__ModifyNetwork()
        self.__UpdateDictionary()

        self.__CreateBusObjects()
        self.__dssSolver.reSolve()

        if self.__Options and self.__Options['Log Results']:
            self.ResultContainer = RC(kwargs, self.__dssPath,
                                      self.__dssObjects, self.__dssObjectsByClass, self.__dssBuses, self.__dssSolver)

        pyCtrlReader = pcr(self.__dssPath['pyControllers'])
        ControllerList = pyCtrlReader.pyControllers
        if ControllerList is not None:
            self.__CreateControllers(ControllerList)


        pyPlotReader = ppr(self.__dssPath['pyPlots'])
        PlotList = pyPlotReader.pyPlots
        if PlotList is not None and not all(value == False for value in kwargs.values()):
            self.__CreatePlots(PlotList)

        for Plot in self.__pyPlotObjects:
            self.BokehSessionID = self.__pyPlotObjects[Plot].GetSessionID()
            if kwargs['Open plots in browser']:
                self.__pyPlotObjects[Plot].session.show()
            break

        return

    def __ModifyNetwork(self):
        # self.__Modifier.Add_Elements('Storage', {'bus' : ['storagebus'], 'kWRated' : ['2000'], 'kWhRated'  : ['2000']},
        #                              True, self.__dssObjects)
        # self.__Modifier.Edit_Elements('regcontrol', 'enabled' ,'False')
        #self.__Modifier.Edit_Elements('Load', 'enabled', 'False')
        return

    def __CreateControllers(self, ControllerDict):
        self.__pyControls = {}

        for ControllerType, ElementsDict in ControllerDict.items():
            for ElmName, SettingsDict in ElementsDict.items():
                 Controller = pyControllers.pyController.Create(ElmName, ControllerType, SettingsDict, self.__dssObjects,
                                                  self.__dssInstance, self.__dssSolver)
                 if Controller != -1:
                    self.__pyControls['Controller.' + ElmName] = Controller
                    self.__Logger.info('Created pyController -> Controller.' + ElmName)
        return

    def __CreatePlots(self, PlotsDict):
        for PlotType, PlotNames in PlotsDict.items():
            newPlotNames = list(PlotNames)
            PlotType1= ['Network layout', 'GIS overlay']
            PlotType2 = ['Sag plot', 'Histogram']
            PlotType3 = ['XY plot', 'Time series']
            for Name in newPlotNames:
                PlotSettings = PlotNames[Name]
                PlotSettings['FileName'] = Name
                if PlotType in PlotType1 and self.__Options[PlotType]:
                    self.__pyPlotObjects[PlotType] = PyPlots.pyPlots.Create(PlotType, PlotSettings,self.__dssBuses,
                                                                    self.__dssObjectsByClass,self.__dssCircuit)
                    self.__Logger.info('Created pyPlot -> ' + PlotType)
                elif PlotType in PlotType2 and self.__Options[PlotType]:
                    self.__pyPlotObjects[PlotType + Name] = PyPlots.pyPlots.Create(PlotType, PlotSettings,self.__dssBuses,
                                                                           self.__dssObjectsByClass, self.__dssCircuit)
                    self.__Logger.info('Created pyPlot -> ' + PlotType)
                elif PlotType in PlotType3  and self.__Options[PlotType]:
                    self.__pyPlotObjects[PlotType+Name] = PyPlots.pyPlots.Create(PlotType, PlotSettings,self.__dssBuses,
                                                                         self.__dssObjects, self.__dssCircuit)
                    self.__Logger.info('Created pyPlot -> ' + PlotType)
        return

    def __UpdateControllers(self, Priority, Time, UpdateResults):
        error = 0
        for controller in self.__pyControls.values():
            error += controller.Update(Priority, Time, UpdateResults)
        return abs(error) < self.__Options['Error tolerance'], error

    def __CreateBusObjects(self):
        BusNames = self.__dssCircuit.AllBusNames()
        for BusName in BusNames:
            self.__dssCircuit.SetActiveBus(BusName)
            self.__dssBuses[BusName] = dssBus(self.__dssInstance)
        return

    def __UpdateDictionary(self):
        InvalidSelection = ['Settings', 'ActiveClass', 'dss', 'utils', 'PDElements', 'XYCurves', 'Bus', 'Properties']
        self.__dssObjectsByClass={'LoadShape' : self.__GetRelaventObjectDict('LoadShape')}

        for ElmName in self.__dssInstance.Circuit.AllElementNames():
            Class, Name =  ElmName.split('.', 1)
            if Class + 's' not in self.__dssObjectsByClass:
                self.__dssObjectsByClass[Class + 's'] = {}
            self.__dssInstance.Circuit.SetActiveElement(ElmName)
            self.__dssObjectsByClass[Class + 's'][ElmName] = dssElement(self.__dssInstance)
            self.__dssObjects[ElmName] = self.__dssObjectsByClass[Class + 's'][ElmName]

        for ObjName in self.__dssObjects.keys():
            Class = ObjName.split('.')[0] + 's'
            if Class not in self.__dssObjectsByClass:
                self.__dssObjectsByClass[Class] = {}
            if  ObjName not in self.__dssObjectsByClass[Class]:
                self.__dssObjectsByClass[Class][ObjName] = self.__dssObjects[ObjName]

        self.__dssObjects['Circuit.' + self.__dssCircuit.Name()] = dssCircuit(self.__dssInstance)
        self.__dssObjectsByClass['Circuits'] = {
            'Circuit.' + self.__dssCircuit.Name() : self.__dssObjects['Circuit.' + self.__dssCircuit.Name()]
        }
        return

    def __GetRelaventObjectDict(self, key):
        ObjectList = {}
        ElmCollection = getattr(dss, key)
        Elem = ElmCollection.First()
        while Elem:
            ObjectList[self.__dssInstance.Element.Name()] =  dssElement(self.__dssInstance)
            Elem = ElmCollection.Next()
        return ObjectList

    def RunStep(self, step, updateObjects=None):
        print('Running simulation @ time step: ', step)
        if updateObjects:
            for object, params in updateObjects.items():
                cl, name = object.split('.')
                self.__Modifier.Edit_Elements(cl, name, params)
            pass

        self.__dssSolver.IncStep()
        for priority in range(CONTROLLER_PRIORITIES):
            for i in range(self.__Options['Max Control Iterations']):
                has_converged, error = self.__UpdateControllers(priority, step, UpdateResults=False)
                self.__Logger.debug('Control Loop {} convergence error: {}'.format(priority, error))
                if has_converged or i == self.__Options['Max Control Iterations'] - 1:
                    if not has_converged:
                        self.__Logger.warning('Control Loop {} no convergence @ {} '.format(priority, step))
                    break
                self.__dssSolver.reSolve()
            #self.__dssSolver.reSolve()

        self.__UpdatePlots()
        if self.__Options['Log Results']:
            self.ResultContainer.UpdateResults()
        if self.__Options['Return Results']:
            return self.ResultContainer.CurrentResults
        #self.__dssSolver.IncStep()

    def RunSimulation(self):
        startTime = time.time()
        TotalDays = self.__Options['End Day'] - self.__Options['Start Day']
        Steps = int(TotalDays * 24 * 60 / self.__Options['Step resolution (min)'])
        self.__Logger.info('Running simulation for ' + str(Steps) + ' time steps')
        for step in range(Steps):
            self.RunStep(step)

        if self.__Options and self.__Options['Log Results']:
            self.ResultContainer.ExportResults()

        self.__Logger.info('Simulation completed in ' + str(time.time() - startTime) + ' seconds')
        self.__Logger.info('End of simulation')

    def __UpdatePlots(self):
        for Plot in self.__pyPlotObjects:
            self.__pyPlotObjects[Plot].UpdatePlot()
        return

    def DeleteInstance(self):
        self.__DelFlag = 1
        self.__del__()
        return

    def __del__(self):

        x = list(self.__Logger.handlers)
        for i in x:
            self.__Logger.removeHandler(i)
            i.flush()
            i.close()

        if self.__DelFlag == 1:
            self.__Logger.info('An instance of OpenDSS (' + str(self) + ') has been deleted.')
        else:
            self.__Logger.error('An instance of OpenDSS (' + str(self) + ') crashed.')
        return