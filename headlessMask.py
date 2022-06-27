#
# Copyright 2022 Jonathan Schultz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import qgis.core
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge
from PyQt5.QtCore import QFile, QFileInfo, QByteArray, QTextStream, QSettings
from PyQt5.QtXml import QDomDocument
import sys
from os.path import expanduser

# Plugin paths. Currently tested only on Debian. Needs updating for other OSs.
# QGIS should help us here.
sys.path.append('/usr/share/qgis/python/plugins')
sys.path.append(expanduser('~') + '/.local/share/QGIS/QGIS3/profiles/default/python/plugins/')

from mask.aeag_mask import aeag_mask

class QgsApplication(qgis.core.QgsApplication):
  
    class FakeSignal:
        def connect(self, dummy):
            pass

    class FakeInterface:
        def __init__(self, canvas):
            self.canvas = canvas
            self.layoutDesignerClosed = QgsApplication.FakeSignal()
        def activeLayer(self): # used by aeag_mask.py
            return None
        def mapCanvas(self): # used by aeag_mask.py
            return self.canvas

    class FakeQAction:
        def __init__(self):
            pass
        def setEnabled(self, value):
            pass
        def setText(self, value):
            pass

    def __init__(self, *args):
        global globalQgs
        globalQgs = self
        super(QgsApplication, self).__init__(*args)
    
    def initQgis(self):
        super(QgsApplication, self).initQgis()

        # Init Mask plugin
        self.canvas = QgsMapCanvas()
        fakeIface = QgsApplication.FakeInterface(self.canvas)
        QSettings().setValue("locale/userLocale", "C")
        self.mask_plugin = aeag_mask(fakeIface)
        self.mask_plugin.act_aeag_mask = QgsApplication.FakeQAction()

class QgsLayoutManager(qgis.core.QgsLayoutManager):
    def layoutByName(self, name: str):
        global globalQgs
        layout = qgis.core.QgsLayoutManager.layoutByName(self, name)
        if not self.on_layout_added_called:
            self.on_layout_added_called = True
            globalQgs.mask_plugin.on_layout_added(name)
        return layout
        
class QgsProject(qgis.core.QgsProject):
  
    def instance():
        self = qgis.core.QgsProject.instance()
        self.__class__ = QgsProject
        return self
        
    def read(self, filename: str):
        global globalQgs
        projectAsFile = QFile(filename)
        projectAsDocument = QDomDocument()
        projectAsDocument.setContent(projectAsFile)
        composerAsNode = projectAsDocument.elementsByTagName("Composer").at(0)
        composerAsString = QByteArray()
        composerAsNode.save(QTextStream(composerAsString), 2)
        composerAsDocument = QDomDocument()
        composerAsDocument.setContent(composerAsString)
        
        super(QgsProject, self).read(filename)

        globalQgs.mask_plugin.registry = QgsProject.instance()
        globalQgs.mask_plugin.on_project_open()

        bridge = QgsLayerTreeMapCanvasBridge(
            QgsProject.instance().layerTreeRoot(), globalQgs.canvas)
        bridge.setCanvasLayers()
        
    def layoutManager(self):
        manager = qgis.core.QgsProject.layoutManager(self)
        if manager.__class__ == qgis.core.QgsLayoutManager:
            manager.__class__ = QgsLayoutManager
            manager.on_layout_added_called = False
        return manager