bl_info={
	"name": "Blueprint Builder",
	"author": "emburcke",
	"version": (1,0,2),
	"blender": (3, 6, 0),
	"location": "View3D -> N-Panel -> Create",
	"description": "it join objects and triangulate them by blueprint",
	"warning": "I worked under blender 3.6.11. other blender versions may be not supported.",
	"category": "Add Mesh",
	"doc_url": "example.com",
	"tracker_url": "example.com"
}

import bpy
import bmesh
import mathutils
import random
import math
import sys

# setting up log

debugg=False

if debugg:
	if "Builder.log" in bpy.data.texts:
		out=bpy.data.texts["Builder.log"]
	else :
		out=bpy.data.texts.new("Builder.log")
	sys.stdout=sys.stderr=out

def isbuilder(actor):
	if isinstance(actor,str):
		actor=bpy.data.objects[actor]
	if "BD_object" in actor:
		return bool(actor["BD_object"])
	else :
		return False

def gettype(actor):
	try :
		return actor.BD_data.BD_Type
	except :
		return None

def getchilds(actor):
	if isinstance(actor,str):
		actor=bpy.data.objects[actor]
	return actor.children

def dividevector(a,b):
	return mathutils.Vector([a[0]/b[0], a[1] / b[1] , a[2] / b[2]])

def recalc_matrix(actor): # TODO nem igy kell recalcolni a matrixot !!!!! keresd az offical modot, mivel ez bugos lehet.!!!
	"""wrote by emburcke in a very boring day.
	this was the only thing i can do,so i debugged with a questionable mindset
	how the matrix build up from rotation location and scale.
	ther isn't any proof that this is work, so be carefull with it!!!
	edit: learned about it. this matrix is equal to rotation matrix * scale matrix * move matrix;
	still there isn't any proof that blender uses only theese attributes to build this matrix."""
	rot=actor.rotation_euler.to_matrix()
	loc=actor.location
	sca=actor.scale
	matrix=mathutils.Matrix([
	  [rot[0][0] * sca[0] ,rot[0][1]          ,rot[0][2]          ,loc[0]],
	  [rot[1][0]          ,rot[1][1] * sca[1] ,rot[1][2]          ,loc[1]],
	  [rot[2][0]          ,rot[2][1]          ,rot[2][2] * sca[2] ,loc[2]],
	  [0.0                ,0.0                ,0.0                ,1.0   ]])
	return matrix

def parent(parent,children):
	children.parent=parent
	children.matrix_parent_inverse = recalc_matrix(parent).inverted()

def UnparentAndKeep(children):
	parented_wm = children.matrix_world.copy()
	children.parent = None
	children.matrix_world = parented_wm

def joinobjects(objects,context): # the first is the active object.
	override=context.copy()
	override['active_object']=objects[0] # override['object']=
	override['selected_editable_objects']=objects # override['selected_objects']=
	with context.temp_override(**override):
		bpy.ops.object.join()

def get_world_location(actor):
	return actor.matrix_world.to_translation()

def get_world_rotation(actor):
	return actor.matrix_world.to_euler()

def fillchilds(self,context,actor,tempcoll,last=None): # TODO nem kell megmutatni a temp collection-t es gyorsabb lesz.
	for i in getchilds(actor):
		if not isbuilder(i):
			fillchilds(self,context,i,tempcoll,last)
			continue
		if gettype(i) == "container":
			self.report({'WARNING'},"Container named '" + i.name + "' inside an another container")
			continue
		elif gettype(i) == "importer":
			if None is i.BD_data.BD_Include:
				self.report({'WARNING'},"Container Referer named '" + i.name+ "' Does Not Contain a Container reference")
				fillchilds(self,context,i,tempcoll,last)
				continue
			mesh=compile(self,context,i.BD_data.BD_Include,[i.BD_data.BD_Include],"") # nincs vertex group elonev, mivel ez csak prebuild.
			mesh.location=get_world_location(i)
			mesh.rotation_euler=get_world_rotation(i)
			tempcoll.objects.link(mesh)
		elif gettype(i) == "origin":
			if None is i.BD_data.BD_Mesh:
				self.report({'WARNING'},"Mesh Referer named '" + i.name+ "' Does Not Contain a Mesh reference")
				fillchilds(self,context,i,tempcoll,last)
				continue
			mesh=i.BD_data.BD_Mesh.copy()
			mesh.location=get_world_location(i)
			mesh.rotation_euler=get_world_rotation(i)
			tempcoll.objects.link(mesh)
		if None is not last:
			parent(last,mesh)
		fillchilds(self,context,i,tempcoll,mesh)

def triangulate(obj,threshold=1e-17): # keeps the legal 4 gons. (the 4 vertives is in one plain) # TODO paraméterezheto legyen!
	bm=bmesh.new()
	bm.from_mesh(obj.data)
	faces=list()
	for i in bm.faces:
		if len(i.verts) == 4:
			if True : # BUGOS ES ATENGED NEHANY ROSZ NEGYEST(i.verts[1].co - i.verts[0].co) .cross(i.verts[2].co - i.verts[0].co).normalized().dot( (i.verts[3].co - i.verts[0].co).normalized() ) > 0:
				faces.append(i)
		elif len(i.verts) > 4:
			faces.append(i)
	bmesh.ops.triangulate(bm,faces=faces)
	bm.to_mesh(obj.data)
	bm.free()

def addvertexall(obj,name,must_new=False): # return the created vertex_group. if the must_new is true alwalys create a new group.
	if (not must_new) and (name in obj.vertex_groups):
		group=obj.vertex_groups[name]
	else :
		group=obj.vertex_groups.new(name=name)
	group.add(range(len(obj.data.vertices)),1,"ADD")
	return group

def assistcompile(self,context,actor,tempcoll,prefix,incompile):
	print("BD::DEBUGG assistcompile called with actor=",actor,"incompile=",incompile)
	for i in getchilds(actor):
		print("BD::DEBUGG started a new for. child=",i,"actor=",actor)
		if not isbuilder(i):
			assistcompile(self,context,i,tempcoll,prefix,incompile)
			continue
		if gettype(i) == "container":
			self.report({'WARNING'},"Container named '" + i.name + "' inside an another container")
			continue
		elif gettype(i) == "importer":
			if None is i.BD_data.BD_Include:
				self.report({'WARNING'},"Container Referer named '" + i.name+ "' Does Not Contain a Container reference")
				assistcompile(self,context,i,tempcoll,prefix,incompile)
				continue
			if i.BD_data.BD_Include in incompile:
				self.reprort({'ERROR'},"Cyclic reference Error: Container named '" + i.name + "' called again while still in compile, ignoring it.")
				context.window_manager.popup_menu(lambda self,context: self.layout.label(text=("Cyclic reference Error: Container named '" + i.name + "' called again while still in compile, ignoring it.")),title="Error",icon="ERROR")
				assistcompile(self,context,i,tempcoll,prefix,incompile)
				continue
			mesh=compile(self,context,i.BD_data.BD_Include,incompile + [i.BD_data.BD_Include],prefix + "::" + i.BD_data.BD_VertexGroup)
			mesh.location=get_world_location(i)
			mesh.rotation_euler=get_world_rotation(i)
			tempcoll.objects.link(mesh)
		elif gettype(i) == "origin":
			if None is i.BD_data.BD_Mesh:
				self.report({'WARNING'},"Mesh Referer named '" + i.name+ "' Does Not Contain a Mesh reference")
				assistcompile(self,context,i,tempcoll,prefix,incompile)
				continue
			mesh=bpy.data.objects.new(i.BD_data.BD_Mesh.name,i.BD_data.BD_Mesh.data.copy()) # TODO modifiers !!. ide is meg a sima copyhoz is !!.
			if i.BD_data.BD_VertexGroup:
				nprefix=prefix + "::" + i.BD_data.BD_VertexGroup
			else :
				nprefix=prefix
			addvertexall(mesh,nprefix)
			mesh.location=get_world_location(i)
			mesh.rotation_euler=get_world_rotation(i)
			tempcoll.objects.link(mesh)
		assistcompile(self,context,i,tempcoll,nprefix,incompile)

def compile(self,context,actor,incompile,prefix=""):
	print("BD::DEBUGG compile called with actor=",actor,"incompile=",incompile,"prefix=",repr(prefix))
	"return object"
	fillneed=None
	if actor.BD_data.BD_VertexGroup:
		if prefix:
			prefix = prefix + "::" + actor.BD_data.BD_VertexGroup
		else :
			prefix=actor.BD_data.BD_VertexGroup
	else :
		fillneed=prefix
		prefix=""
	assistcompile(self,context,actor,actor.BD_data.BD_TempCollection,prefix,incompile)
	origin=bpy.data.objects.new("origin",bpy.data.meshes.new("origin"))
	origin.location=get_world_location(actor)
	print("BD:DEBUGG COMPILE origin.location=",origin.location)
	origin.rotation_euler=get_world_rotation(actor)

	# RECALC AND UPDATE MATRIX AND APPLY TO THE OBJECT. (why dont update the matrix yourself blender?; - hamlet)
	origin.matrix_world=recalc_matrix(origin)


	objects=[origin]
	for i in actor.BD_data.BD_TempCollection.objects:
		objects.append(i)
	joinobjects(objects,context)
	origin.data.use_auto_smooth=True
	origin.data.auto_smooth_angle=math.radians(30) # TODO paraméterezheto legyen!
	if None is not fillneed: # adding prefix before all vertex groups.
		maingroup=addvertexall(origin,actor.name,must_new=True).name
		if fillneed == "":
			prefix=maingroup
		else :
			prefix=fillneed + "::" + maingroup
		translate=dict()
		while True:
			fill="%016X_" % random.randint(0,2**64-1)
			if fill not in origin.vertex_groups:
				break
		for i in origin.vertex_groups:
			before=i.name
			i.name=fill
			translate[i.name]=before
		for i in translate:
			if translate[i] == maingroup:
				if fillneed:
					translate[i] = fillneed + "::" + translate[i]
			else :
				translate[i]=prefix + translate[i]
		for i in origin.vertex_groups:
			i.name=translate[i.name]
	triangulate(origin)
	return origin
	# TODO, bone generation, es meg korrabbra, a join ele. material baking, es texturing.

# BLENDER api

classes=list()
custom_registers=list()

# blender class definitons
def register():
	for cls in classes:
		bpy.utils.register_class(cls)
	for reg, unreg in custom_registers:
		reg()

def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
	for reg, unreg in custom_registers:
		unreg()

# operators

class MESH_OT_Add_BD_object(bpy.types.Operator):
	"""Add a new Blueprint Builder Container."""
	bl_idname="mesh.add_bd_container"
	bl_label="bd_addcontainer"

	def execute(self, context):
		new_data=context.scene.BD_new_data
		if new_data.BD_Type == "container":
			empty=bpy.data.objects.new(context.scene.BD_new_container_name,None)
			empty.empty_display_type='CUBE'
			empty.BD_data.BD_Type="container"
			empty.BD_data.BD_TempCollection=new_data.BD_TempCollection
			empty.BD_data.BD_VertexGroup=new_data.BD_VertexGroup
			if None is empty.BD_data.BD_TempCollection:
				collection=bpy.data.collections.new("BD_TempCollection")
				context.scene.collection.children.link(collection)
				empty.BD_data.BD_TempCollection=collection
				self.report({'INFO'},"Active Builder Container's temp collection is not set. setting to='" + collection.name + "'")
		elif new_data.BD_Type == "origin":
			empty=bpy.data.objects.new(context.scene.BD_new_origin_name,None)
			empty.empty_display_type='PLAIN_AXES'
			empty.BD_data.BD_Type="origin"
			empty.BD_data.BD_Mesh=new_data.BD_Mesh
			empty.BD_data.BD_VertexGroup=new_data.BD_VertexGroup
		elif new_data.BD_Type == "importer":
			empty=bpy.data.objects.new(context.scene.BD_new_importer_name,None)
			empty.empty_display_type='ARROWS'
			empty.BD_data.BD_Type="importer"
			empty.BD_data.BD_Include=new_data.BD_Include
			empty.BD_data.BD_VertexGroup=new_data.BD_VertexGroup
		empty['BD_object']=True
		new_data.BD_VertexGroup="" # resetting the vertex group name
		context.collection.objects.link(empty)
		return {'FINISHED'}

classes.append(MESH_OT_Add_BD_object)

class OBJECT_OT_Precompile_Container(bpy.types.Operator):
	"""Precompile an existing Blueprint Builder Container."""
	bl_idname="mesh.bd_precompile_container"
	bl_label="bd_precompile"

	def execute(self, context):
		actor=context.active_object
		if None is actor:
			return {'PASS_THROUGH'}
		if not isbuilder(actor):
			sefl.report({'INFO'},"Active object is not a Builder object")
			return {'PASS_THROUGH'}
		if gettype(actor) != "container":
			sefl.report({'WARNING'},"Active Builder object is not a container")
			return {'CANCELLED'}
		if None is actor.BD_data.BD_TempCollection:
			collection=bpy.data.collections.new("BD_TempCollection")
			context.scene.collection.children.link(collection)
			actor.BD_data.BD_TempCollection=collection
			self.report({'INFO'},"Active Builder Container's temp collection is not set. setting to='" + collection.name + "'")
		for i in actor.BD_data.BD_TempCollection.objects:
			bpy.data.objects.remove(i)
		fillchilds(self,context,actor,actor.BD_data.BD_TempCollection,actor)
		return {'FINISHED'}
classes.append(OBJECT_OT_Precompile_Container)

class OBJECT_OT_Compile_Container(bpy.types.Operator):
	"""Compile an existing Blueprint Builder Container."""
	bl_idname="mesh.bd_compile_container"
	bl_label="bd_compile"

	def execute(self, context):
		actor=context.active_object
		if None is actor:
			return {'PASS_THROUGH'}
		if not isbuilder(actor):
			sefl.report({'INFO'},"Active object is not a Builder object")
			return {'PASS_THROUGH'}
		if gettype(actor) != "container":
			sefl.report({'WARNING'},"Active Builder object is not a container")
			return {'CANCELLED'}
		if None is actor.BD_data.BD_TempCollection:
			collection=bpy.data.collections.new("BD_TempCollection")
			context.scene.collection.children.link(collection)
			actor.BD_data.BD_TempCollection=collection
			self.report({'INFO'},"Active Builder Container's temp collection is not set. setting to='" + collection.name + "'")
		for i in actor.BD_data.BD_TempCollection.objects:
			bpy.data.objects.remove(i)
		context.collection.objects.link(compile(self,context,actor,[actor]))
		return {'FINISHED'}
classes.append(OBJECT_OT_Compile_Container)

class OBJECT_OT_Free_Temp(bpy.types.Operator):
	"""Deletes all object(s) in the temporary container."""
	bl_idname="mesh.bd_freetemp"
	bl_label="bd_freetemp"
	def execute(self, context):
		actor=context.active_object
		if None is actor:
			return {'PASS_THROUGH'}
		if not isbuilder(actor):
			sefl.report({'INFO'},"Active object is not a Builder object")
			return {'PASS_THROUGH'}
		if gettype(actor) != "container":
			sefl.report({'WARNING'},"Active Builder object is not a container")
			return {'CANCELLED'}
		if None is actor.BD_data.BD_TempCollection:
			collection=bpy.data.collections.new("BD_TempCollection")
			context.scene.collection.children.link(collection)
			actor.BD_data.BD_TempCollection=collection
			self.report({'INFO'},"Active Builder Container's temp collection is not set. setting to='" + collection.name + "'")
		else:
			for i in actor.BD_data.BD_TempCollection.objects:
				bpy.data.objects.remove(i)
		return {'FINISHED'}
classes.append(OBJECT_OT_Free_Temp)

# properties

class BlueprintBuilderPropertiesGroup(bpy.types.PropertyGroup):
	BD_Type: bpy.props.EnumProperty(
		name="Type",
		default="container",
		items=[
				("container", "Container", "Contains a blueprint", 0),
				("origin", "Origin", "Refers to a mesh", 1),
				("importer", "Importer", "Refers to an another container", 2)
		],
		description="The Builder Ojbect type"
	)
	BD_TempCollection: bpy.props.PointerProperty(
		type=bpy.types.Collection,
		name="Temp Collection",
	)

	BD_Mesh: bpy.props.PointerProperty(
		type=bpy.types.Object,
		name="Referred Mesh",
		poll=lambda self,ob: (ob and (ob.type == 'MESH'))
	)

	BD_Include: bpy.props.PointerProperty(
		type=bpy.types.Object,
		name="Included Container",
		poll=lambda self,ob: (ob and isbuilder(ob) and (gettype(ob) == 'container')) 
	)
	BD_VertexGroup: bpy.props.StringProperty(
		name="Group",
		default="",
		description="keep empty for use default"
	)

classes.insert(0,BlueprintBuilderPropertiesGroup)

def register_BlueprintPropery():
	bpy.types.Object.BD_data=bpy.props.PointerProperty(
			type=BlueprintBuilderPropertiesGroup,
			name="BlueprintBuilder",
			description="Blueprint Builder Object properties"
		)
	bpy.types.Scene.BD_new_data=bpy.props.PointerProperty(
			type=BlueprintBuilderPropertiesGroup,
			name="BlueprintBuilder",
			description="Blueprint Builder Object properties"
		)

def unregister_BlueprintPropery():
	del bpy.types.Object.BD_data
	del bpy.types.Scene.BD_new_data

custom_registers.append((register_BlueprintPropery,unregister_BlueprintPropery))

# panels
class BuilderConstructerPanel(bpy.types.Panel):
	bl_category = "Create"
	bl_label = "Blueprint Builder"
	bl_idname = "OBJECT_PT_Blueprint_Builder_addpanel"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_context = "objectmode"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		new_data=context.scene.BD_new_data
		col = self.layout.column(align=True)
		col.prop(new_data,"BD_Type")
		if new_data.BD_Type == "container":
			col.prop(context.scene,"BD_new_container_name")
			col.prop(new_data, "BD_TempCollection")
			col.prop(new_data, "BD_VertexGroup")
		elif new_data.BD_Type == "origin":
			col.prop(context.scene,"BD_new_origin_name")
			col.prop(new_data, "BD_Mesh")
			col.prop(new_data, "BD_VertexGroup")
		elif new_data.BD_Type == "importer":
			col.prop(context.scene,"BD_new_importer_name")
			col.prop(new_data,"BD_Include")
			col.prop(new_data, "BD_VertexGroup",text="Group prefix")
		col.operator(MESH_OT_Add_BD_object.bl_idname, text="Add New BD Object")

classes.append(BuilderConstructerPanel)

def register_BD_new_name():
	bpy.types.Scene.BD_new_container_name=bpy.props.StringProperty(
		name="Name",
		default="BD_Container",
		description="Name of the new Container"
	)
	bpy.types.Scene.BD_new_origin_name=bpy.props.StringProperty(
		name="Name",
		default="BD_Origin",
		description="Name of the new Origin"
	)
	bpy.types.Scene.BD_new_importer_name=bpy.props.StringProperty(
		name="Name",
		default="BD_Importer",
		description="Name of the new Importer"
	)

def unregister_BD_new_name():
	del bpy.types.Scene.BD_new_container_name
	del bpy.types.Scene.BD_new_origin_name
	del bpy.types.Scene.BD_new_importer_name

custom_registers.append((register_BD_new_name,unregister_BD_new_name))

class ExistingBuilderPanel(bpy.types.Panel):
	bl_category = "Create"
	bl_label = "Blueprint Builder Settings"
	bl_idname = "OBJECT_PT_Blueprint_Builder_Settings"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_context = "objectmode"
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		actor=context.active_object
		if actor.BD_data.BD_Type == "container":
			col = self.layout.column(align=True)
			col.label(text="Compiling:")
			col.operator(OBJECT_OT_Compile_Container.bl_idname, text="Compile active Container")
			col.operator(OBJECT_OT_Precompile_Container.bl_idname, text="Precompile active Container")
			col.operator(OBJECT_OT_Free_Temp.bl_idname, text="Del Compiled Objects")
			col = self.layout.column(align=True)
			col.label(text="Container Settings:")
			col.prop(actor, "name")
			col.prop(actor.BD_data, "BD_TempCollection")
			col.prop(actor.BD_data, "BD_VertexGroup")
		elif actor.BD_data.BD_Type == "origin":
			col = self.layout.column(align=True)
			col.label(text="Origin Settings:")
			col.prop(actor, "name")
			col.prop(actor.BD_data, "BD_Mesh")
			col.prop(actor.BD_data, "BD_VertexGroup")
		elif actor.BD_data.BD_Type == "importer":
			col = self.layout.column(align=True)
			col.label(text="Importer Settings:")
			col.prop(actor, "name")
			col.prop(actor.BD_data, "BD_Include")
			col.prop(actor.BD_data, "BD_VertexGroup",text="Group prefix")
			

	@classmethod
	def poll(cls, context):
		ob = bpy.context.active_object
		return (ob and isbuilder(ob))

classes.append(ExistingBuilderPanel)


if __name__ == "__main__":
	register()
