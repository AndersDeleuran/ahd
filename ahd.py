"""
Utility functions for writing GHPython scripts
Author: Anders Holden Deleuran
Version: 200811
"""

import time
import math
from scriptcontext import sticky as st
import Rhino as rc
import Grasshopper as gh
import GhPython
import datetime
import rhinoscriptsyntax as rs
from System.Drawing import Color
import scriptcontext as sc

class Timer(object):
    
    """ A simple profiler """
    
    def start(self):

        # Start the timer
        self.startTime = time.time()
        
    def stop(self):
        
        # Print an return elapsed time
        elapsedSeconds = time.time() - self.startTime
        elapsedMilliseconds = elapsedSeconds*1000
        print str(round(elapsedMilliseconds,3)) + " ms"
        return elapsedMilliseconds

def listToTree(nestedList):
    
    """ Convert a nested python iterable to a datatree """
    
    dt = gh.DataTree[object]()
    for i,l in enumerate(nestedList):
        dt.AddRange(l,gh.Kernel.Data.GH_Path(i))
        
    return dt

def customDisplay(toggle,component):
    
    """ Make a custom display which is unique to the component and lives in sticky """
    
    # Make unique name and custom display
    displayGuid = "customDisplay_" + str(component.InstanceGuid)
    if displayGuid not in st:
        st[displayGuid] = rc.Display.CustomDisplay(True)
        
    # Clear display each time component runs
    st[displayGuid].Clear()
    
    # Return the display or get rid of it
    if toggle:
        return st[displayGuid]
    else:
        st[displayGuid].Dispose()
        del st[displayGuid]
        return None

def killCustomDisplays():
    
    """ Clear any custom displays living in the Python sticky dictionary """
    
    for k,v in st.items():
        if type(v) is rc.Display.CustomDisplay:
            v.Dispose()
            del st[k]

def remapValues(values,targetMin,targetMax,srcMin,srcMax):
    
    """ Remaps a list of values to the new domain targetMin-targetMax """
    
    #srcMin = min(values)
    #srcMax = max(values)
    
    if srcMax-srcMin > 0:
        remappedValues = []
        for v in values:
            rv = ((v-srcMin)/(srcMax-srcMin))*(targetMax-targetMin)+targetMin
            remappedValues.append(rv)
    else:
        meanVal = (targetMin+targetMax)/2
        remappedValues = [meanVal for i in range(len(values))]
        
    return remappedValues

def valuesToColors(values):
    
    """ Make a list of HSL colors, meaning that 0.0: red and 0.6: blue """
    
    colors = []
    for v in values:
        rcColor = rc.Display.ColorHSL(v,1.0,0.5)
        colors.append(rcColor)
        
    return colors

def sampleColorSpectrum(colors,t,smooth):
    
    """ Interpolate along multiple colors by 0.00-1.00 parameter t """
    
    if t <= 0.0:
        return colors[0]
    elif t >= 1.0:
        return colors[-1]
    else:
        
        # Compute spectrum t, starting color, and local t
        tSpectrum = t * (len(colors)-1)
        colorID = int(math.floor(tSpectrum))
        tLocal = tSpectrum-colorID
        
        # Use cosine interpolation (see paulbourke.net/miscellaneous/interpolation)
        if smooth:
            tLocal = (1-math.cos(tLocal*math.pi))/2
            
        # Blend colors
        cA = rc.Display.Color4f(colors[colorID])
        cB = rc.Display.Color4f(colors[colorID+1])
        cC = cA.BlendTo(tLocal,cB)
        blendColor = cC.AsSystemColor()
        
        return blendColor

def colorMeshFaces_V5(mesh,colors):
    
    """ Unwelds and color the faces of a mesh """
    
    # Get faces/vertices
    faces = mesh.Faces
    vertices = mesh.Vertices
    
    # Make empty mesh and face-vertex ID counter 
    cMesh = rc.Geometry.Mesh()
    fID = 0
    for i in range(faces.Count):
        
        # Get face and color
        f = faces[i]
        c = colors[i]
        
        # Add face vertices and colors to empty cMesh
        cMesh.Vertices.Add(vertices[f.A])
        cMesh.Vertices.Add(vertices[f.B])
        cMesh.Vertices.Add(vertices[f.C])
        cMesh.VertexColors.Add(c)
        cMesh.VertexColors.Add(c)
        cMesh.VertexColors.Add(c)
        if f.IsQuad:
            cMesh.Vertices.Add(vertices[f.D])
            cMesh.VertexColors.Add(c)
            
       # Add face
        if f.IsQuad:
            cMesh.Faces.AddFace(fID,fID+1,fID+2,fID+3)
            fID += 4
        elif f.IsTriangle:
            cMesh.Faces.AddFace(fID,fID+1,fID+2)
            fID += 3
            
    return cMesh

def colorMeshFaces_V6(mesh,colors):
    
    """ Unwelds and color the faces of the mesh in place """
    
    mesh.VertexColors.CreateMonotoneMesh(System.Drawing.Color.Black)
    mesh.Unweld(0,False)
    for i in range(mesh.Faces.Count):
        mesh.VertexColors.SetColor(mesh.Faces[i],colors[i])

def makeLegendParams(capLower,capUpper,hueLower,hueUpper,count):
    
    """ Make a list of data following the Ladybug format,
    used for generating a CustomVectorLegend """
    
    hues = floatRange(hueLower,hueUpper,count-1)
    colors = valuesToColors(hues)
    lp = [capLower,capUpper,None,colors]
    return lp

def updateComponent(ghenv,interval):
    
    """ Updates this component, similar to using a grasshopper timer """
    
    # Define callback action
    def callBack(e):
        ghenv.Component.ExpireSolution(False)
        
    # Get grasshopper document
    ghDoc = ghenv.Component.OnPingDocument()
    
    # Schedule this component to expire
    ghDoc.ScheduleSolution(interval,gh.Kernel.GH_Document.GH_ScheduleDelegate(callBack))

def buildDocString_LEGACY(ghenv):
    
    """ Builds a documentation string by iterating the component
    (i.e. ghenv.Component) input and outputs parameters """
    
    # Add component description string
    ds = '"""\n'
    ds += "Write main component documentation here.\n"
    
    # Add input parameter type properties
    ds += "    Inputs:\n"
    for v in ghenv.Component.Params.Input:
        dataType = str(v.TypeHint.TypeName).lower()
        vd = list(v.VolatileData.AllData(False))
        if vd and dataType == "system.object":
            vdType = str(vd[0].GetType())
            vdType = vdType.split(".")[-1]
            dataType = vdType.strip("GH_").lower()
        ds += "        " + v.Name + ": {" + str(v.Access).lower() + "," + dataType + "}\n"
        
    # Add output parameter type properties
    ds += "    Outputs:\n"
    for v in ghenv.Component.Params.Output:
        ds += "        " + v.Name + ": \n"
        # print globals()[v.Name]
        
    # Add author, Rhino, and script version
    ds += "    Remarks:\n"
    ds += "        Author: Anders Holden Deleuran (BIG IDEAS)\n"
    ds += "        Rhino: " + str(rc.RhinoApp.Version) + "\n"
    ds += "        Version: " + str(datetime.date.today()).replace("-","")[2:] + "\n"
    ds += '"""'
    
    print ds
    return ds

def getParameterProperties(p,globalsDict):
    
    """ Extract a component parameter name, access, and data type """

    # Get name, data and set initial type
    pName = p.Name
    pData = globalsDict[pName]
    pDataType = None

    # Determine access and data type
    if type(pData) is list:
        pAccess = "list"
        if pData:
            pDataType = type(pData[0])
    elif type(pData) is gh.DataTree[object]:
        pAccess = "tree"
        if pData: 
            pDataType = type(pData.AllData()[0])
    else:
        pAccess = "item"
        if pData is not None:
            pDataType = type(pData)
        
    # Format data type string
    if pDataType:
        pDataType = pDataType.__name__.lower()
    else:
        pDataType = "?"
    
    return pName,pAccess,pDataType

def buildDocString(globalsDict):
    
    """ Builds a documentation string by iterating the ghenv.Component input
    and outputs parameters. Call with globals() as input at very end of script """

    # Get ghenv
    ghenv = globalsDict["ghenv"]
    
    # Add component description string
    ds = '"""\n'
    ds += "Write main component documentation here.\n"
    
    # Add input parameter type properties
    ds += "    Inputs:\n"
    for p in ghenv.Component.Params.Input:
        pName,pAccess,pDataType = getParameterProperties(p,globalsDict)
        ds += "        " + pName + ": {" + pAccess + "," + pDataType + "}\n"
        
    # Add output parameter type properties
    ds += "    Outputs:\n"
    for p in ghenv.Component.Params.Output:
        pName,pAccess,pDataType = getParameterProperties(p,globalsDict)
        ds += "        " + pName + ": {" + pAccess + "," + pDataType + "}\n"
        
    # Add author, Rhino, and script version
    ds += "    Remarks:\n"
    ds += "        Author: Anders Holden Deleuran (BIG IDEAS)\n"
    ds += "        Rhino: " + str(rc.RhinoApp.Version) + "\n"
    ds += "        Version: " + str(datetime.date.today()).replace("-","")[2:] + "\n"
    ds += '"""'
    
    print ds
    return ds

def setParametersToDrawName(ghenv):
    
    """ Set all canvas parameters to always draw name """
    
    for obj in ghenv.Component.OnPingDocument().Objects:
        if obj.GetType().Namespace == "Grasshopper.Kernel.Parameters":
            obj.IconDisplayMode = gh.Kernel.GH_IconDisplayMode.name
            obj.ExpireSolution(True)

def setNoTypeHint(ghenv):
    
    """ Set all input parameters to No Type Hint, DO NOT USE YET!!"""
    
    for v in ghenv.Component.Params.Input:
        v.TypeHint = GhPython.Component.NoChangeHint()
    ghenv.Component.ExpireSolution(False)

def setTemplateLayerColors():

    """ Set Rhino layer colors to the AHD style """

    # Set context to Rhino document and disable redraw
    sc.doc = rc.RhinoDoc.ActiveDoc
    rs.EnableRedraw(False)

    # Set layer colors
    for i,l in enumerate(rs.LayerNames()):
        if i == 0:
            rs.LayerColor (l,Color.FromArgb(255,105,105,105))   
        elif i == 1:
            rs.LayerColor (l,Color.FromArgb(255,255,0,90))    
        elif i == 2:
            rs.LayerColor (l,Color.FromArgb(255,70,190,190))   
        elif i == 3:
            rs.LayerColor (l,Color.FromArgb(255,0,85,255))
        elif i == 4:
            rs.LayerColor (l,Color.FromArgb(255,130,255,0))
        elif i == 5:
            rs.LayerColor (l,Color.FromArgb(255,190,190,190))

def capValues(values,lower,upper):
    
    """ Cap values that are smaller than lower and larger than upper """
    
    capped = []
    for v in values:
        if v < lower:
            capped.append(lower)
        elif v > upper:
            capped.append(upper)
        else:
            capped.append(v)
            
    return capped

def floatRange(start,stop,steps):
    
    """ Generate a range of floats, similar to Grasshoppers Range """
    
    stepSize = (stop-start)/steps
    values = [start]
    for i in range(1,steps):
        values.append(i*stepSize+start)
    values.append(stop)
    
    return values

def closestValue(v,values):
    
    """ Find the value that is closest to v in values """
    
    i = bisect.bisect_left(values,v)
    if i == len(values):
        return i-1
    elif values[i] == v:
        return i
    elif i > 0:
        j = i-1
        if values[i] - v > v - values[j]:
            return j
    return i

def discretiseValues(values,steps):
    
    """ Bin/bucket/discretise a list of values into N steps """
    
    # Calculate the bin values
    bins = floatRange(min(values),max(values),int(Steps))
    bins.sort()
    
    # Find the closest bin for each value
    closestBins = [closestValue(v,bins) for v in values]
    
    return closestBins

def meshGrid(points,ptsU,ptsV):
    
    """ Make a quad mesh from a grid of points """ 
    
    if len(points) == ptsU*ptsV:
        
        # Make mesh and add vertices
        mesh = rc.Geometry.Mesh()
        mesh.Vertices.AddVertices(rc.Collections.Point3dList(points))
        
        # Add faces
        for i in range(ptsU-1):
            for j in range(0,ptsU*(ptsV-1),ptsU):
                ij = i+j
                mesh.Faces.AddFace(ij, ij+ptsU, ij+ptsU+1, ij+1)
                
        # Compute normals and return
        mesh.Normals.ComputeNormals()
        
        return mesh

def ghSolutionRecompute(ghenv):
    
    """ Recomputes the Grasshopper solution (ala pressing F5) """
    
    def expireAllComponentsButThis(e):
        for obj in ghenv.Component.OnPingDocument().Objects:
            if not obj.InstanceGuid == ghenv.Component.InstanceGuid:
                obj.ExpireSolution(False)
                
    ghenv.Component.OnPingDocument().ScheduleSolution(1000,expireAllComponentsButThis)