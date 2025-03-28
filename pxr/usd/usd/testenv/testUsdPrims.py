#!/pxrpythonsubst
#
# Copyright 2017 Pixar
#
# Licensed under the terms set forth in the LICENSE.txt file available at
# https://openusd.org/license.

from __future__ import print_function

import sys, unittest
from pxr import Sdf,Usd,Tf

allFormats = ['usd' + x for x in 'ac']

class TestUsdPrim(unittest.TestCase):
    def test_Basic(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('Basics.'+fmt)
            p = s.GetPrimAtPath('/')
            q = s.GetPrimAtPath('/')
            assert p is not q
            assert p == q
            assert hash(p) == hash(q)

            # Check that unicode objects convert to sdfpaths.
            #
            # In python 3 all strings are unicode, but we want to keep these
            # explicit unicode strings so we don't lose coverage in python 2
            # tests.
            p = s.GetPrimAtPath(u'/')
            q = s.GetPrimAtPath(u'/')
            assert p is not q
            assert p == q
            assert hash(p) == hash(q)

            p = s.OverridePrim('/foo')
            p.CreateAttribute('attr', Sdf.ValueTypeNames.String)
            a = p.GetAttribute('attr')
            b = p.GetAttribute('attr')
            assert a and b
            assert a is not b
            assert a == b
            assert hash(a) == hash(b)
            assert not a.HasFallbackValue()
            assert not b.HasFallbackValue()

            p.CreateRelationship('relationship')
            a = p.GetRelationship('relationship')
            b = p.GetRelationship('relationship')
            assert a and b
            assert a is not b
            assert a == b
            assert hash(a) == hash(b)

            # check for prims/props that exist
            p = s.GetObjectAtPath(u'/foo')
            assert p
            assert type(p) is Usd.Prim

            a = s.GetObjectAtPath(u'/foo.attr')
            assert a
            assert type(a) is Usd.Attribute

            r = s.GetObjectAtPath(u'/foo.relationship')
            assert r 
            assert type(r) is Usd.Relationship

            # check for prims/props that dont exist
            p = s.GetObjectAtPath(u'/nonexistent')
            assert not p
            assert type(p) is Usd.Prim

            a = s.GetObjectAtPath(u'/foo.nonexistentattr')
            assert not a
            assert type(a) is Usd.Property

            r = s.GetObjectAtPath(u'/foo.nonexistentrelationship')
            assert not r 
            assert type(r) is Usd.Property


    def test_OverrideMetadata(self):
        for fmt in allFormats:
            weak = Sdf.Layer.CreateAnonymous('OverrideMetadataTest.'+fmt)
            strong = Sdf.Layer.CreateAnonymous('OverrideMetadataTest.'+fmt)
            stage = Usd.Stage.Open(weak.identifier)
            assert stage.DefinePrim("/Mesh/Child", "Mesh")

            stage = Usd.Stage.Open(strong.identifier)

            p = stage.OverridePrim("/Mesh")
            p.GetReferences().AddReference(Sdf.Reference(weak.identifier, "/Mesh"))
            p = stage.GetPrimAtPath("/Mesh/Child")
            assert p
            assert p.SetMetadata(
                "hidden", False), "Failed to set metadata in stronger layer" 
            assert p.GetName() == p.GetPath().name

    def test_GetPrimStack(self):
        layers = [Sdf.Layer.CreateAnonymous('base.usda'),
                  Sdf.Layer.CreateAnonymous('sublayer.usda'),
                  Sdf.Layer.CreateAnonymous('payload.usda'),
                  Sdf.Layer.CreateAnonymous('basic_over.usda')]

        base = layers[0]
        sublayer = layers[1]
        payload = layers[2]
        basicOver = layers[3]

        primPath = '/root'

        stage = Usd.Stage.Open(sublayer)
        over = stage.OverridePrim(primPath)

        stage = Usd.Stage.Open(basicOver)
        over = stage.OverridePrim(primPath)

        stage = Usd.Stage.Open(payload)
        over = stage.OverridePrim(primPath)
        over.GetReferences().AddReference(
            Sdf.Reference(basicOver.identifier, primPath, 
                          Sdf.LayerOffset(0.0, 2.0)))

        stage = Usd.Stage.Open(base)
        prim = stage.DefinePrim(primPath)
        prim.GetPayloads().AddPayload(
            Sdf.Payload(payload.identifier, primPath, Sdf.LayerOffset(10.0)))
        stage.GetRootLayer().subLayerPaths.append(sublayer.identifier) 
        stage.GetRootLayer().subLayerOffsets[0] = Sdf.LayerOffset(20.0)

        expectedPrimStack = [layer.GetPrimAtPath(primPath) for layer in layers]
        stage = Usd.Stage.Open(base)
        prim = stage.GetPrimAtPath(primPath)

        assert prim.GetPrimStack() == expectedPrimStack

        expectedPrimStackWithLayerOffsets = [
            (expectedPrimStack[0], Sdf.LayerOffset()),
            (expectedPrimStack[1], Sdf.LayerOffset(20.0)),
            (expectedPrimStack[2], Sdf.LayerOffset(10.0)),
            (expectedPrimStack[3], Sdf.LayerOffset(10.0, 2.0)),
        ]
        assert (prim.GetPrimStackWithLayerOffsets() == 
                    expectedPrimStackWithLayerOffsets)

    def test_GetCachedPrimBits(self):
        layerFile = 'test.usda'
        layer = Sdf.Layer.FindOrOpen(layerFile)
        assert layer, 'failed to find "%s"' % layerFile

        stage = Usd.Stage.Open(layer, load=Usd.Stage.LoadNone)
        assert stage, 'failed to create stage for %s' % layerFile

        # Check various bits.
        root = stage.GetPrimAtPath('/')
        globalClass = stage.GetPrimAtPath('/GlobalClass')
        abstractSubscope = stage.GetPrimAtPath('/GlobalClass/AbstractSubscope')
        abstractOver = stage.GetPrimAtPath('/GlobalClass/AbstractOver')
        pureOver = stage.GetPrimAtPath('/PureOver')
        undefSubscope = stage.GetPrimAtPath('/PureOver/UndefinedSubscope')
        group = stage.GetPrimAtPath('/Group')
        modelChild = stage.GetPrimAtPath('/Group/ModelChild')
        localChild = stage.GetPrimAtPath('/Group/LocalChild')
        undefModelChild = stage.GetPrimAtPath('/Group/UndefinedModelChild')
        deactivatedScope = stage.GetPrimAtPath('/Group/DeactivatedScope')
        deactivatedModel = stage.GetPrimAtPath('/Group/DeactivatedModel')
        deactivatedOver = stage.GetPrimAtPath('/Group/DeactivatedOver')
        propertyOrder = stage.GetPrimAtPath('/PropertyOrder')

        # Named child access API
        assert group.GetChild('ModelChild') == modelChild
        assert group.GetChild('LocalChild') == localChild
        assert not group.GetChild('__NoSuchChild__')

        # Check filtered children access.
        self.assertEqual(list(root.GetAllChildren()), [
            globalClass, pureOver, group, propertyOrder])
        self.assertEqual(list(root.GetChildren()), [propertyOrder])

        def _TestFilteredChildren(predicate, expectedChildren):
            self.assertEqual(list(root.GetFilteredChildren(predicate)), 
                             expectedChildren)
            self.assertEqual(list(root.GetFilteredChildrenNames(predicate)), 
                             [c.GetName() for c in expectedChildren])

        # Manually construct the "normal" view using the default predicate.
        _TestFilteredChildren(Usd.PrimDefaultPredicate, [propertyOrder])

        # Manually construct the "normal" view using the individual terms
        # from the default predicate.
        _TestFilteredChildren(
            Usd.PrimIsActive & Usd.PrimIsLoaded &
            Usd.PrimIsDefined & ~Usd.PrimIsAbstract, [propertyOrder])

        # Only abstract prims.
        _TestFilteredChildren(Usd.PrimIsAbstract, [globalClass])

        # Abstract & defined prims -- still just the class.
        _TestFilteredChildren(
            Usd.PrimIsAbstract & Usd.PrimIsDefined, [globalClass])

        # Abstract | unloaded prims -- the class and the group.
        _TestFilteredChildren(
            Usd.PrimIsAbstract | ~Usd.PrimIsLoaded, [globalClass, group])

        # Models only.
        _TestFilteredChildren(Usd.PrimIsModel, [group])

        # Non-models only.
        _TestFilteredChildren(~Usd.PrimIsModel,
                    [globalClass, pureOver, propertyOrder])

        # Models or undefined.
        _TestFilteredChildren(
            Usd.PrimIsModel | ~Usd.PrimIsDefined, [pureOver, group])

        # Check individual flags.
        assert root.IsActive()
        assert root.IsLoaded()
        assert root.IsModel()
        assert root.IsGroup()
        assert not root.IsAbstract()
        assert root.IsDefined()
        assert root.HasDefiningSpecifier()
        assert root.GetSpecifier() == Sdf.SpecifierDef

        assert globalClass.IsActive()
        assert globalClass.IsLoaded()
        assert not globalClass.IsModel()
        assert not globalClass.IsGroup()
        assert globalClass.IsAbstract()
        assert globalClass.IsDefined()
        assert globalClass.HasDefiningSpecifier()
        assert globalClass.GetSpecifier() == Sdf.SpecifierClass

        assert abstractSubscope.IsActive()
        assert abstractSubscope.IsLoaded()
        assert not abstractSubscope.IsModel()
        assert not abstractSubscope.IsGroup()
        assert abstractSubscope.IsAbstract()
        assert abstractSubscope.IsDefined()
        assert abstractSubscope.HasDefiningSpecifier()
        assert abstractSubscope.GetSpecifier() == Sdf.SpecifierDef

        assert abstractOver.IsActive()
        assert abstractOver.IsLoaded()
        assert not abstractOver.IsModel()
        assert not abstractOver.IsGroup()
        assert abstractOver.IsAbstract()
        assert not abstractOver.IsDefined()
        assert not abstractOver.HasDefiningSpecifier()
        assert abstractOver.GetSpecifier() == Sdf.SpecifierOver

        assert pureOver.IsActive()
        assert pureOver.IsLoaded()
        assert not pureOver.IsModel()
        assert not pureOver.IsGroup()
        assert not pureOver.IsAbstract()
        assert not pureOver.IsDefined()
        assert not pureOver.HasDefiningSpecifier()
        assert pureOver.GetSpecifier() == Sdf.SpecifierOver

        assert undefSubscope.IsActive()
        assert undefSubscope.IsLoaded()
        assert not undefSubscope.IsModel()
        assert not undefSubscope.IsGroup()
        assert not undefSubscope.IsAbstract()
        assert not undefSubscope.IsDefined()
        assert undefSubscope.HasDefiningSpecifier()
        assert undefSubscope.GetSpecifier() == Sdf.SpecifierDef

        assert group.IsActive()
        assert not group.IsLoaded()
        assert group.IsModel()
        assert group.IsGroup()
        assert not group.IsAbstract()
        assert group.IsDefined()
        assert group.HasDefiningSpecifier()
        assert group.GetSpecifier() == Sdf.SpecifierDef

        assert modelChild.IsActive()
        assert not modelChild.IsLoaded()
        assert modelChild.IsModel()
        assert not modelChild.IsGroup()
        assert not modelChild.IsAbstract()
        assert modelChild.IsDefined()
        assert modelChild.HasDefiningSpecifier()
        assert modelChild.GetSpecifier() == Sdf.SpecifierDef

        assert localChild.IsActive()
        assert not localChild.IsLoaded()
        assert not localChild.IsModel()
        assert not localChild.IsGroup()
        assert not localChild.IsAbstract()
        assert localChild.IsDefined()
        assert localChild.HasDefiningSpecifier()
        assert localChild.GetSpecifier() == Sdf.SpecifierDef

        assert undefModelChild.IsActive()
        assert not undefModelChild.IsLoaded()
        assert not undefModelChild.IsModel()
        assert not undefModelChild.IsGroup()
        assert not undefModelChild.IsAbstract()
        assert not undefModelChild.IsDefined()
        assert not undefModelChild.HasDefiningSpecifier()
        assert undefModelChild.GetSpecifier() == Sdf.SpecifierOver

        assert not deactivatedScope.IsActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        # activate it.
        deactivatedScope.SetActive(True)
        assert deactivatedScope.IsActive()
        assert deactivatedScope.HasAuthoredActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        # clear active.
        deactivatedScope.ClearActive()
        assert deactivatedScope.IsActive()
        assert not deactivatedScope.HasAuthoredActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        # deactivate it again.
        deactivatedScope.SetActive(False)
        assert not deactivatedScope.IsActive()
        assert deactivatedScope.HasAuthoredActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        assert not deactivatedModel.IsActive()
        assert not deactivatedModel.IsLoaded()
        assert deactivatedModel.IsModel()
        assert not deactivatedModel.IsGroup()
        assert not deactivatedModel.IsAbstract()
        assert deactivatedModel.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedModel.GetPath().AppendChild('child'))

        assert not deactivatedOver.IsActive()
        assert not deactivatedOver.IsLoaded()
        assert not deactivatedOver.IsModel()
        assert not deactivatedOver.IsGroup()
        assert not deactivatedOver.IsAbstract()
        assert not deactivatedOver.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedOver.GetPath().AppendChild('child'))

        # Load the model and recheck.
        stage.Load('/Group')

        assert group.IsActive()
        assert group.IsLoaded()
        assert group.IsModel()
        assert group.IsGroup()
        assert not group.IsAbstract()
        assert group.IsDefined()
        assert group.HasDefiningSpecifier()
        assert group.GetSpecifier() == Sdf.SpecifierDef

        # child should be loaded now.
        assert localChild.IsActive()
        assert localChild.IsLoaded()
        assert not localChild.IsModel()
        assert not localChild.IsGroup()
        assert not localChild.IsAbstract()
        assert localChild.IsDefined()
        assert localChild.HasDefiningSpecifier()
        assert localChild.GetSpecifier() == Sdf.SpecifierDef

        # undef child should be loaded and defined, due to payload inclusion.
        assert undefModelChild.IsActive()
        assert undefModelChild.IsLoaded()
        assert not undefModelChild.IsModel()
        assert not undefModelChild.IsGroup()
        assert not undefModelChild.IsAbstract()
        assert undefModelChild.IsDefined()

        # check prim defined entirely inside payload.
        payloadChild = stage.GetPrimAtPath('/Group/PayloadChild')
        assert payloadChild
        assert payloadChild.IsActive()
        assert payloadChild.IsLoaded()
        assert not payloadChild.IsModel()
        assert not payloadChild.IsGroup()
        assert not payloadChild.IsAbstract()
        assert payloadChild.IsDefined()
        assert undefModelChild.HasDefiningSpecifier()
        assert undefModelChild.GetSpecifier() == Sdf.SpecifierDef

        # check deactivated scope again.
        assert not deactivatedScope.IsActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        # activate it.
        deactivatedScope.SetActive(True)
        assert deactivatedScope.IsActive()
        assert deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))

        # deactivate it again.
        deactivatedScope.SetActive(False)
        assert not deactivatedScope.IsActive()
        assert not deactivatedScope.IsLoaded()
        assert not deactivatedScope.IsModel()
        assert not deactivatedScope.IsGroup()
        assert not deactivatedScope.IsAbstract()
        assert deactivatedScope.IsDefined()
        assert deactivatedScope.HasDefiningSpecifier()
        assert deactivatedScope.GetSpecifier() == Sdf.SpecifierDef
        assert not stage.GetPrimAtPath(
            deactivatedScope.GetPath().AppendChild('child'))


    def test_ChangeTypeName(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('ChangeTypeName.'+fmt)
            foo = s.OverridePrim("/Foo")

            # Initialize
            self.assertEqual(foo.GetTypeName(), "")
            self.assertEqual(foo.GetMetadata("typeName"), None)
            assert not foo.HasAuthoredTypeName()

            # Set via public API 
            assert foo.SetTypeName("Mesh")
            assert foo.HasAuthoredTypeName()
            self.assertEqual(foo.GetTypeName(), "Mesh")
            self.assertEqual(foo.GetMetadata("typeName"), "Mesh")
            self.assertEqual(foo.GetTypeName(), "Mesh")

            foo.ClearTypeName()
            self.assertEqual(foo.GetTypeName(), "")
            self.assertEqual(foo.GetMetadata("typeName"), None)
            assert not foo.HasAuthoredTypeName()

            # Set via metadata
            assert foo.SetMetadata("typeName", "Scope")
            assert foo.HasAuthoredTypeName()
            self.assertEqual(foo.GetTypeName(), "Scope")
            self.assertEqual(foo.GetMetadata("typeName"), "Scope")

    def test_HasAuthoredReferences(self):
        for fmt in allFormats:
            s1 = Usd.Stage.CreateInMemory('HasAuthoredReferences.'+fmt)
            s1.DefinePrim("/Foo", "Mesh")
            s1.DefinePrim("/Bar", "Mesh")
            baz = s1.DefinePrim("/Foo/Baz", "Mesh")
            assert baz.GetReferences().AddReference(s1.GetRootLayer().identifier, "/Bar")

            s2 = Usd.Stage.CreateInMemory('HasAuthoredReferences.'+fmt)
            foo = s2.OverridePrim("/Foo")
            baz = s2.GetPrimAtPath("/Foo/Baz")

            assert not baz
            assert not foo.HasAuthoredReferences()
            assert foo.GetReferences().AddReference(s1.GetRootLayer().identifier, "/Foo")
            items = foo.GetMetadata("references").ApplyOperations([])
            assert foo.HasAuthoredReferences()

            # Make sure references are detected across composition arcs.
            baz = s2.OverridePrim("/Foo/Baz")
            assert baz.HasAuthoredReferences()

            # Clear references out.
            assert foo.GetReferences().ClearReferences()
            assert not foo.HasAuthoredReferences()
            # Child should be gone.
            baz = s2.GetPrimAtPath("/Foo/Baz")
            assert not baz

            # Set the references explicitly.
            assert foo.GetReferences().SetReferences(items)
            assert foo.HasAuthoredReferences()
            # Child is back.
            baz = s2.GetPrimAtPath("/Foo/Baz")
            assert baz.HasAuthoredReferences()

            # Explicitly set references to the empty list. The metadata will
            # still exist as an explicitly empty list op.
            assert foo.GetReferences().SetReferences([])
            assert foo.HasAuthoredReferences()
            # Child should be gone.
            baz = s2.GetPrimAtPath("/Foo/Baz")
            assert not baz

            # Clear references out. Still empty but no longer explicit.
            assert foo.GetReferences().ClearReferences()
            assert not foo.HasAuthoredReferences()
            # Child still gone.
            baz = s2.GetPrimAtPath("/Foo/Baz")
            assert not baz

            # Explicitly set references to the empty again from cleared
            # verifying that it is indeed set to explicit.
            assert foo.GetReferences().SetReferences([])
            assert foo.HasAuthoredReferences()
            # Child is not back.
            baz = s2.GetPrimAtPath("/Foo/Baz")
            assert not baz

    def test_GoodAndBadReferences(self):
        for fmt in allFormats:
            # Sub-root references are allowed
            s1 = Usd.Stage.CreateInMemory('References.'+fmt)
            s1.DefinePrim("/Foo", "Mesh")
            s1.DefinePrim("/Bar/Bazzle", "Mesh")
            baz = s1.DefinePrim("/Foo/Baz", "Mesh")
            bazRefs = baz.GetReferences()
            bazRefs.AddReference(s1.GetRootLayer().identifier, "/Bar/Bazzle")

            # Test that both in-memory identifiers, relative paths, and absolute
            # paths all resolve properly
            s2 = Usd.Stage.CreateNew("refTest1."+fmt)
            sphere = s2.DefinePrim("/Sphere", "Sphere")
            sphereRefs = sphere.GetReferences()
            s3 = Usd.Stage.CreateNew("refTest2."+fmt)
            box = s3.DefinePrim("/Box", "Cube")
            self.assertEqual(s2.ResolveIdentifierToEditTarget(
                s1.GetRootLayer().identifier), s1.GetRootLayer().identifier)
            self.assertNotEqual(s2.ResolveIdentifierToEditTarget(
                "./refTest2."+fmt), "")
            self.assertNotEqual(s2.ResolveIdentifierToEditTarget(
                s2.GetRootLayer().realPath), "")
            # but paths to non-existent files fail
            self.assertEqual(s2.ResolveIdentifierToEditTarget("./noFile."+fmt), "")
            # paths relative to in-memory layers resolve relative to the cwd
            # (under the default resolver)
            self.assertNotEqual(s1.ResolveIdentifierToEditTarget("./refTest2."+fmt), "")

            # A good reference generates no errors or exceptions
            assert bazRefs.AddReference(s2.GetRootLayer().identifier, "/Sphere")

            # A bad reference succeeds, but generates warnings from compose errors.
            assert not sphere.HasAuthoredReferences()
            assert sphereRefs.AddReference("./refTest2."+fmt, "/noSuchPrim")
            assert sphere.HasAuthoredReferences()

    def test_PropertyOrder(self):
        layerFile = 'test.usda'
        layer = Sdf.Layer.FindOrOpen(layerFile)
        assert layer, 'failed to find "%s"' % layerFile

        stage = Usd.Stage.Open(layer, load=Usd.Stage.LoadNone)
        assert stage, 'failed to create stage for %s' % layerFile

        po = stage.GetPrimAtPath('/PropertyOrder')
        assert po
        attrs = po.GetAttributes()
        # expected order:
        expected = ['A0', 'a1', 'a2', 'A3', 'a4', 'a5', 'a10', 'A20']
        assert [a.GetName() for a in attrs] == expected, \
            '%s != %s' % ([a.GetName() for a in attrs], expected)

        rels = po.GetRelationships()
        # expected order:
        expected = ['R0', 'r1', 'r2', 'R3', 'r4', 'r5', 'r10', 'R20']
        assert [r.GetName() for r in rels] == expected, \
            '%s != %s' % ([r.GetName() for r in rels], expected)
        
        
    def test_PropertyReorder(self):
        def l(chars):
            return list(x for x in chars)

        for fmt in allFormats:
            sl = Sdf.Layer.CreateAnonymous(fmt)
            s = Usd.Stage.CreateInMemory('PropertyReorder.'+fmt, sl)
            f = s.OverridePrim('/foo')

            s.SetEditTarget(s.GetRootLayer())
            for name in reversed(l('abcd')):
                f.CreateAttribute(name, Sdf.ValueTypeNames.Int)

            s.SetEditTarget(s.GetSessionLayer())
            for name in reversed(l('defg')):
                f.CreateAttribute(name, Sdf.ValueTypeNames.Int)

            self.assertEqual(f.GetPropertyNames(), l('abcdefg'))

            pred = lambda tok : tok in ['a', 'd', 'f']
            self.assertEqual(f.GetPropertyNames(predicate=pred),
                             l('adf'))

            f.SetPropertyOrder(l('edc'))
            self.assertEqual(f.GetPropertyNames(), l('edcabfg'))

            f.SetPropertyOrder(l('a'))
            self.assertEqual(f.GetPropertyNames(), l('abcdefg'))

            f.SetPropertyOrder([])
            self.assertEqual(f.GetPropertyNames(), l('abcdefg'))

            f.SetPropertyOrder(l('g'))
            self.assertEqual(f.GetPropertyNames(), l('gabcdef'))

            f.SetPropertyOrder(l('d'))
            self.assertEqual(f.GetPropertyNames(), l('dabcefg'))

            self.assertEqual(f.GetPropertyNames(predicate=pred),
                             l('daf'))

            f.SetPropertyOrder(l('xyz'))
            self.assertEqual(f.GetPropertyNames(), l('abcdefg'))

            f.SetPropertyOrder(l('xcydze'))
            self.assertEqual(f.GetPropertyNames(), l('cdeabfg'))

            f.SetPropertyOrder(l('gfedcba'))
            self.assertEqual(f.GetPropertyNames(), l('gfedcba'))

            f.ClearPropertyOrder()
            self.assertEqual(f.GetPropertyNames(), l('abcdefg'))

    def test_ChildrenReorder(self):
        def l(chars):
            return list(x for x in chars)

        def _TestAllChildren(p, expectedNames):
            self.assertEqual(p.GetAllChildrenNames(), expectedNames)
            self.assertEqual(p.GetAllChildren(), 
                             [p.GetChild(name) for name in expectedNames])

        def _TestChildren(p, expectedNames):
            self.assertEqual(p.GetChildrenNames(), expectedNames)
            self.assertEqual(p.GetChildren(), 
                             [p.GetChild(name) for name in expectedNames])

        def _TestOrder(s, parentPath):

            f = s.DefinePrim(parentPath) if parentPath else s.GetPseudoRoot()

            s.SetEditTarget(s.GetRootLayer())
            for name in l('abcd'):
                s.DefinePrim(parentPath + '/' + name)

            s.SetEditTarget(s.GetSessionLayer())
            for name in l('defg'):
                s.OverridePrim(parentPath + '/' + name)

            # Start with no primOrder set. Default order.
            self.assertIsNone(f.GetMetadata("primOrder"))
            self.assertEqual(f.GetChildrenReorder(), [])
            _TestAllChildren(f, l('abcdefg'))
            _TestChildren(f, l('abcd'))

            # Set partial ordering. 
            f.SetChildrenReorder(l('edc'))
            self.assertEqual(f.GetMetadata("primOrder"), l('edc'))
            self.assertEqual(f.GetChildrenReorder(), l('edc'))
            _TestAllChildren(f, l('abefgdc'))
            _TestChildren(f, l('abdc'))

            # Empty ordering. Back to default order.
            f.SetChildrenReorder([])
            self.assertEqual(f.GetMetadata("primOrder"), [])
            self.assertEqual(f.GetChildrenReorder(), [])
            _TestAllChildren(f, l('abcdefg'))
            _TestChildren(f, l('abcd'))

            # Single entry in order. Still maintains default ordering.
            f.SetChildrenReorder(l('d'))
            self.assertEqual(f.GetMetadata("primOrder"), l('d'))
            self.assertEqual(f.GetChildrenReorder(), l('d'))
            _TestAllChildren(f, l('abcdefg'))
            _TestChildren(f, l('abcd'))

            # Set ordering with no valid names. Default ordering.
            f.SetChildrenReorder(l('xyz'))
            self.assertEqual(f.GetMetadata("primOrder"), l('xyz'))
            self.assertEqual(f.GetChildrenReorder(), l('xyz'))
            _TestAllChildren(f, l('abcdefg'))
            _TestChildren(f, l('abcd'))

            # Set reorder with interspersed invalid names. Reorders with just 
            # the valid names.
            f.SetChildrenReorder(l('xeydzc'))
            self.assertEqual(f.GetMetadata("primOrder"), l('xeydzc'))
            self.assertEqual(f.GetChildrenReorder(), l('xeydzc'))
            _TestAllChildren(f, l('abefgdc'))
            _TestChildren(f, l('abdc'))

            # Full reorder containing all the child prims.
            f.SetChildrenReorder(l('gfedcba'))
            self.assertEqual(f.GetMetadata("primOrder"), l('gfedcba'))
            self.assertEqual(f.GetChildrenReorder(), l('gfedcba'))
            _TestAllChildren(f, l('gfedcba'))
            _TestChildren(f, l('dcba'))

            # Clear the reorder on the session layer. Return to original order.
            f.ClearChildrenReorder()
            self.assertIsNone(f.GetMetadata("primOrder"))
            self.assertEqual(f.GetChildrenReorder(), [])
            _TestAllChildren(f, l('abcdefg'))
            _TestChildren(f, l('abcd'))

            # Do a full reorder on the root layer.
            with Usd.EditContext(s, s.GetRootLayer()):
                f.SetChildrenReorder(l('gfedcba'))
            self.assertEqual(f.GetMetadata("primOrder"), l('gfedcba'))
            self.assertEqual(f.GetChildrenReorder(), l('gfedcba'))
            # Because the reorder is authored on the root layer, it only 
            # reorders the prims that are defined on the root layer because 
            # prim order is processed during composition. The prims defined on
            # the session layer are not reordered.
            _TestAllChildren(f, l('dcbaefg'))
            _TestChildren(f, l('dcba'))

            # Set an empty ordering on session layer. The strongest resolved
            # metadata is now empty, but the reordering from the root layer
            # metadata still takes place.
            f.SetChildrenReorder([])
            self.assertEqual(f.GetMetadata("primOrder"), [])
            self.assertEqual(f.GetChildrenReorder(), [])
            _TestAllChildren(f, l('dcbaefg'))
            _TestChildren(f, l('dcba'))

        for fmt in allFormats:
            sl = Sdf.Layer.CreateAnonymous(fmt)
            s = Usd.Stage.CreateInMemory('PrimReorder.'+fmt, sl)
            # Test the pseudoroot first before testing on a "real" prim parent
            # which gets added as a pseudoroot child.
            _TestOrder(s, '')
            _TestOrder(s, '/foo')

    def test_DefaultPrim(self):
        for fmt in allFormats:
            # No default prim to start.
            s = Usd.Stage.CreateInMemory('DefaultPrim.'+fmt)
            assert not s.GetDefaultPrim()

            # Set defaultPrim metadata on root layer, but no prim in scene
            # description.
            s.GetRootLayer().defaultPrim = 'foo'
            assert not s.GetDefaultPrim()

            # Create the prim, should pick it up.
            fooPrim = s.OverridePrim('/foo')
            assert s.GetDefaultPrim() == fooPrim

            # Change defaultPrim, ensure it picks up again.
            s.GetRootLayer().defaultPrim = 'bar'
            assert not s.GetDefaultPrim()
            barPrim = s.OverridePrim('/bar')
            assert s.GetDefaultPrim() == barPrim

            # Set sub-root prims as default, should pick it up
            s.GetRootLayer().defaultPrim = 'foo/bar'
            assert not s.GetDefaultPrim()
            fooBarPrim = s.OverridePrim('/foo/bar')
            assert s.GetDefaultPrim() == fooBarPrim
            
            # Try error cases
            s.GetRootLayer().defaultPrim = ''
            assert not s.GetDefaultPrim()

            # Try stage-level authoring API.
            s.SetDefaultPrim(fooPrim)
            assert s.GetDefaultPrim() == fooPrim
            assert s.HasDefaultPrim()
            s.ClearDefaultPrim()
            assert not s.GetDefaultPrim()
            assert not s.HasDefaultPrim()

    def test_GetNextSibling(self):
        import random, time
        seed = int(time.time())
        print('GetNextSibling() random seed:', seed)
        random.seed(seed)

        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('GetNextSibling.'+fmt)

            # Create a stage with some prims, some defined, others not, at random.
            names = tuple('abcd')
            def make(stage, names, depth, prefix=None):
                prefix = prefix if prefix else Sdf.Path.absoluteRootPath
                for name in names:
                    if depth:
                        make(stage, names, depth-1, prefix.AppendChild(name))
                    else:
                        if random.random() <= 0.25:
                            s.DefinePrim(prefix)
                        else:
                            s.OverridePrim(prefix)

            # Now walk every prim on the stage, and ensure that obtaining children
            # by GetChildren() and walking siblings via GetNextSibling() returns the
            # same results.
            def test(root):
                def checkKids(p):
                    direct = p.GetChildren()
                    bySib = []
                    if len(direct):
                        bySib.append(direct[0])
                        while bySib[-1].GetNextSibling():
                            bySib.append(bySib[-1].GetNextSibling())
                    self.assertEqual(direct, bySib)
                checkKids(root)
                for child in root.GetChildren():
                    test(child)

            make(s, names, 4)
            test(s.GetPseudoRoot())

    def test_Instanceable(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('Instanceable.'+fmt)
            p = s.DefinePrim('/Instanceable', 'Mesh')
            assert not p.IsInstanceable()
            assert p.GetMetadata('instanceable') == None
            assert not p.HasAuthoredInstanceable()

            p.SetInstanceable(True)
            assert p.IsInstanceable()
            assert p.GetMetadata('instanceable') == True
            assert p.HasAuthoredInstanceable()

            p.SetInstanceable(False)
            assert not p.IsInstanceable()
            assert p.GetMetadata('instanceable') == False
            assert p.HasAuthoredInstanceable()

            p.ClearInstanceable()
            assert not p.IsInstanceable()
            assert p.GetMetadata('instanceable') == None
            assert not p.HasAuthoredInstanceable()

    def test_GetComposedPrimChildrenAsMetadataTest(self):
        stage = Usd.Stage.Open('MilkCartonA.usda')
        self.assertTrue(stage)

        prim = stage.GetPrimAtPath('/MilkCartonA')
        self.assertTrue(prim)

        self.assertEqual(prim.GetAllMetadata()['typeName'], "Xform")

    def test_GetPrimIndex(self):
        def _CreateTestStage(fmt):
            s = Usd.Stage.CreateInMemory('GetPrimIndex.'+fmt)

            c = s.DefinePrim('/Class')

            r = s.DefinePrim('/Ref')
            s.DefinePrim('/Ref/Child')

            p = s.DefinePrim('/Instance')
            p.GetInherits().AddInherit('/Class')
            p.GetReferences().AddInternalReference('/Ref')
            p.SetInstanceable(True)
            return s

        def _ValidatePrimIndexes(prim):
            # Assert that the prim indexes for the prim at this path
            # are valid. Also dump them to a string just to force
            # all nodes in the prim index to be touched.
            self.assertTrue(prim.GetPrimIndex().IsValid())
            self.assertTrue(prim.GetPrimIndex().DumpToString())
            self.assertTrue(prim.ComputeExpandedPrimIndex().IsValid())
            self.assertTrue(prim.ComputeExpandedPrimIndex().DumpToString())

        for fmt in allFormats:
            s = _CreateTestStage(fmt)

            _ValidatePrimIndexes(s.GetPseudoRoot())
            _ValidatePrimIndexes(s.GetPrimAtPath('/Ref'))
            _ValidatePrimIndexes(s.GetPrimAtPath('/Ref/Child'))

            # Prototype prims do not expose a valid prim index, but can still 
            # be used to compute an expanded prim index which is necessary for
            # composition queries.
            prototype = s.GetPrototypes()[0]
            self.assertFalse(prototype.GetPrimIndex().IsValid())
            self.assertFalse(prototype.GetPrimIndex().DumpToString())
            self.assertTrue(prototype.ComputeExpandedPrimIndex().IsValid())
            self.assertTrue(prototype.ComputeExpandedPrimIndex().DumpToString())

            # However, prims beneath prototypes do expose a valid prim index.
            # Note this prim index may change from run to run depending on
            # which is selected as the source for the prototype.
            _ValidatePrimIndexes(prototype.GetChild('Child'))
            
    def test_PseudoRoot(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('PseudoRoot.%s' % fmt)
            w = s.DefinePrim('/World')
            p = s.GetPrimAtPath('/')
            self.assertTrue(p.IsPseudoRoot())
            self.assertTrue(p.IsValid())
            self.assertFalse(Usd.Prim().IsPseudoRoot())
            self.assertFalse(w.IsPseudoRoot())
            self.assertTrue(w.GetParent().IsPseudoRoot())
            self.assertTrue(w.GetParent().IsValid())
            self.assertFalse(p.GetParent().IsPseudoRoot())
            self.assertFalse(p.GetParent().IsValid())

    def test_Deactivation(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('Deactivation.%s' % fmt)
            child = s.DefinePrim('/Root/Group/Child')

            group = s.GetPrimAtPath('/Root/Group')
            self.assertEqual(group.GetAllChildren(), [child])
            self.assertTrue(s._GetPcpCache().FindPrimIndex('/Root/Group/Child'))

            group.SetActive(False)

            # Deactivating a prim removes all of its children from the stage.
            # Note that the deactivated prim itself still exists on the stage;
            # this allows users to reactivate it.
            self.assertEqual(group.GetAllChildren(), [])

            # Deactivating a prim should also cause the underlying prim 
            # indexes for its children to be removed.
            self.assertFalse(
                s._GetPcpCache().FindPrimIndex('/Root/Group/Child'))

    def test_AppliedSchemas(self):
        self.assertTrue(Usd.ModelAPI().IsAPISchema())
        self.assertTrue(Usd.ClipsAPI().IsAPISchema())
        self.assertTrue(Usd.CollectionAPI().IsAPISchema())

        self.assertFalse(Usd.ModelAPI().IsAppliedAPISchema())
        self.assertFalse(Usd.ClipsAPI().IsAppliedAPISchema())
        self.assertTrue(Usd.CollectionAPI().IsAppliedAPISchema())

        self.assertTrue(Usd.CollectionAPI().IsMultipleApplyAPISchema())

        self.assertTrue(
            Usd.CollectionAPI().GetSchemaKind() == Usd.SchemaKind.MultipleApplyAPI)
        self.assertTrue(
            Usd.CollectionAPI().GetSchemaKind() != Usd.SchemaKind.SingleApplyAPI)
        self.assertTrue(
            Usd.ModelAPI().GetSchemaKind() == Usd.SchemaKind.NonAppliedAPI)
        self.assertTrue(
            Usd.ClipsAPI().GetSchemaKind() == Usd.SchemaKind.NonAppliedAPI)

        # Verify that we an exception but don't crash when applying to the 
        # null prim.
        with self.assertRaises(Tf.ErrorException):
            self.assertFalse(Usd.CollectionAPI.Apply(Usd.Prim(), "root"))

        for fmt in allFormats:
            sessionLayer = Sdf.Layer.CreateNew("SessionLayer.%s" % fmt)
            s = Usd.Stage.CreateInMemory('AppliedSchemas.%s' % fmt, sessionLayer)

            s.SetEditTarget(Usd.EditTarget(s.GetRootLayer()))

            world= s.OverridePrim('/world')
            self.assertEqual([], world.GetAppliedSchemas())

            rootCollAPI = Usd.CollectionAPI.Apply(world, "root")
            self.assertTrue(rootCollAPI)

            world = rootCollAPI.GetPrim()
            self.assertTrue(world)

            self.assertTrue(world.HasAPI(Usd.CollectionAPI))

            # HasAPI always returns false (but doesn't error) for types that 
            # aren't applied API schema types.
            self.assertFalse(world.HasAPI(Usd.Typed))
            self.assertFalse(world.HasAPI(Usd.APISchemaBase))
            self.assertFalse(world.HasAPI(Usd.ModelAPI))
            self.assertFalse(world.HasAPI(Sdf.ListOpType))

            self.assertEqual(['CollectionAPI:root'], world.GetAppliedSchemas())

            # Switch the edit target to the session layer and test bug 156929
            s.SetEditTarget(Usd.EditTarget(s.GetSessionLayer()))
            sessionCollAPI = Usd.CollectionAPI.Apply(world, "session")
            self.assertTrue(sessionCollAPI)
            self.assertEqual(['CollectionAPI:session', 'CollectionAPI:root'],
                             world.GetAppliedSchemas())

            self.assertTrue(world.HasAPI(Usd.CollectionAPI))

            # Ensure duplicates aren't picked up
            anotherSessionCollAPI = Usd.CollectionAPI.Apply(world, "session")
            self.assertTrue(anotherSessionCollAPI)
            self.assertEqual(['CollectionAPI:session', 'CollectionAPI:root'],
                             world.GetAppliedSchemas())

            # Add a duplicate in the root layer and ensure that there are no 
            # duplicates in the composed result.
            s.SetEditTarget(Usd.EditTarget(s.GetRootLayer()))
            rootLayerSessionCollAPI = Usd.CollectionAPI.Apply(world, "session")
            self.assertTrue(rootLayerSessionCollAPI)
            self.assertEqual(['CollectionAPI:session', 'CollectionAPI:root'],
                             world.GetAppliedSchemas())

    def test_Bug160615(self):
        for fmt in allFormats:
            s = Usd.Stage.CreateInMemory('Bug160615.%s' % fmt)
            p = s.OverridePrim('/Foo/Bar')
            self.assertTrue(p)

            s.RemovePrim(p.GetPath())
            self.assertFalse(p)

            p = s.OverridePrim('/Foo/Bar')
            self.assertTrue(p)

    def test_GetAtPath(self):
        """Tests accessing UsdObjects of various types on the same stage
        as a prim."""
        for fmt in allFormats:
            stage = Usd.Stage.CreateInMemory('GetAtPath.%s' % fmt)
            child = stage.DefinePrim("/Parent/Child")
            grandchild = stage.DefinePrim("/Parent/Child/Grandchild")
            sibling = stage.DefinePrim("/Parent/Sibling")

            x = sibling.CreateAttribute("x", Sdf.ValueTypeNames.Int)
            y = grandchild.CreateRelationship("y")

            # Double check axioms about prim validity
            self.assertFalse(Usd.Prim())
            self.assertTrue(child)
            self.assertTrue(grandchild)
            self.assertTrue(sibling)
            self.assertTrue(y)
            self.assertTrue(x)
            self.assertFalse(stage.GetPrimAtPath(Sdf.Path.emptyPath))

            # Test relative prim paths
            self.assertEqual(child.GetPrimAtPath("../Sibling"), sibling)
            self.assertEqual(child.GetPrimAtPath("Grandchild"), grandchild)
            self.assertEqual(child.GetPrimAtPath(".."), child.GetParent())

            # Test absolute prim paths
            self.assertEqual(child.GetPrimAtPath("/Parent/Sibling"), sibling)
            self.assertEqual(child.GetPrimAtPath("../Sibling"),
                             child.GetObjectAtPath("../Sibling"))

            # Test invalid paths
            self.assertFalse(child.GetPrimAtPath("../InvalidPath"))

            # Test relative propeties
            self.assertEqual(child.GetRelationshipAtPath("Grandchild.y"), y)
            self.assertEqual(child.GetAttributeAtPath("../Sibling.x"), x)
            self.assertEqual(child.GetPropertyAtPath("Grandchild.y"), y)
            self.assertEqual(child.GetPropertyAtPath("../Sibling.x"), x)

            # Test Absolute propeties
            self.assertEqual(
                child.GetRelationshipAtPath("/Parent/Child/Grandchild.y"), y)
            self.assertEqual(child.GetAttributeAtPath("/Parent/Sibling.x"), x)
            self.assertEqual(
                child.GetPropertyAtPath("/Parent/Child/Grandchild.y"), y)
            self.assertEqual(child.GetPropertyAtPath("/Parent/Sibling.x"), x)
            
            # Test invalid paths
            self.assertFalse(child.GetPropertyAtPath(".z"))
            self.assertFalse(child.GetRelationshipAtPath(".z"))
            self.assertFalse(child.GetAttributeAtPath(".z"))

            # Test valid paths but invalid types
            self.assertFalse(child.GetPrimAtPath("/Parent/Child/Grandchild.y"))
            self.assertFalse(child.GetPrimAtPath("/Parent/Sibling.x"))
            self.assertFalse(
                child.GetAttributeAtPath("/Parent/Child/Grandchild.y"))
            self.assertFalse(child.GetRelationshipAtPath(
                "/Parent/Sibling.x"))
            self.assertFalse(child.GetAttributeAtPath(
                "/Parent/Child/Grandchild"))
            self.assertFalse(child.GetRelationshipAtPath(
                "/Parent/Sibling"))

            # Test that empty paths don't raise exceptions
            # NOTE-- this is intentionally different than SdfPrimSpec
            # for symmetry with UsdStage's API
            self.assertFalse(child.GetPrimAtPath(Sdf.Path.emptyPath))
            self.assertFalse(child.GetObjectAtPath(Sdf.Path.emptyPath))
            self.assertFalse(child.GetPropertyAtPath(Sdf.Path.emptyPath))
            self.assertFalse(child.GetAttributeAtPath(Sdf.Path.emptyPath))
            self.assertFalse(child.GetRelationshipAtPath(Sdf.Path.emptyPath))
            
            # Verify type deduction
            self.assertTrue(
                isinstance(child.GetObjectAtPath("../Sibling"), Usd.Prim))
            self.assertTrue(
                isinstance(child.GetObjectAtPath("../Sibling.x"),
                Usd.Attribute))
            self.assertTrue(
                isinstance(child.GetObjectAtPath("Grandchild.y"),
                Usd.Relationship))
            self.assertTrue(
                isinstance(child.GetPropertyAtPath("../Sibling.x"),
                Usd.Attribute))
            self.assertTrue(
                isinstance(child.GetPropertyAtPath("Grandchild.y"),
                Usd.Relationship))

    def test_GetDescription(self):
        rootLayer = Sdf.Layer.CreateAnonymous(".usda")
        rootLayer.ImportFromString("""
        #usda 1.0

        def Scope "Ref"
        { 
            def Scope "Child"
            {
            }
        }

        def Scope "Instance" (
            instanceable = True
            references = </Ref>
        )
        {
        }
        """.strip())

        s = Usd.Stage.Open(rootLayer)

        basic = s.GetPrimAtPath("/Ref")
        basicChild = basic.GetChild("Child")

        instance = s.GetPrimAtPath("/Instance")
        instanceProxyChild = instance.GetChild("Child")

        prototype = instance.GetPrototype()
        prototypeChild = prototype.GetChild("Child")

        print(basic.GetDescription())
        print(basicChild.GetDescription())
        print(instance.GetDescription())
        print(instanceProxyChild.GetDescription())
        print(prototype.GetDescription())
        print(prototypeChild.GetDescription())

        # Drop the Usd.Stage and ensure GetDescription on the now-expired
        # Usd.Prims does not crash.
        del s

        print(basic.GetDescription())
        print(basicChild.GetDescription())
        print(instance.GetDescription())
        print(instanceProxyChild.GetDescription())
        print(prototype.GetDescription())
        print(prototypeChild.GetDescription())

if __name__ == "__main__":
    unittest.main()
