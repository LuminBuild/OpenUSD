//
// Copyright 2016 Pixar
//
// Licensed under the terms set forth in the LICENSE.txt file available at
// https://openusd.org/license.
//
#include "pxr/usd/usdGeom/imageable.h"
#include "pxr/usd/usd/schemaRegistry.h"
#include "pxr/usd/usd/typed.h"

#include "pxr/usd/sdf/types.h"
#include "pxr/usd/sdf/assetPath.h"

PXR_NAMESPACE_OPEN_SCOPE

// Register the schema with the TfType system.
TF_REGISTRY_FUNCTION(TfType)
{
    TfType::Define<UsdGeomImageable,
        TfType::Bases< UsdTyped > >();
    
}

/* virtual */
UsdGeomImageable::~UsdGeomImageable()
{
}

/* static */
UsdGeomImageable
UsdGeomImageable::Get(const UsdStagePtr &stage, const SdfPath &path)
{
    if (!stage) {
        TF_CODING_ERROR("Invalid stage");
        return UsdGeomImageable();
    }
    return UsdGeomImageable(stage->GetPrimAtPath(path));
}


/* virtual */
UsdSchemaKind UsdGeomImageable::_GetSchemaKind() const
{
    return UsdGeomImageable::schemaKind;
}

/* static */
const TfType &
UsdGeomImageable::_GetStaticTfType()
{
    static TfType tfType = TfType::Find<UsdGeomImageable>();
    return tfType;
}

/* static */
bool 
UsdGeomImageable::_IsTypedSchema()
{
    static bool isTyped = _GetStaticTfType().IsA<UsdTyped>();
    return isTyped;
}

/* virtual */
const TfType &
UsdGeomImageable::_GetTfType() const
{
    return _GetStaticTfType();
}

UsdAttribute
UsdGeomImageable::GetVisibilityAttr() const
{
    return GetPrim().GetAttribute(UsdGeomTokens->visibility);
}

UsdAttribute
UsdGeomImageable::CreateVisibilityAttr(VtValue const &defaultValue, bool writeSparsely) const
{
    return UsdSchemaBase::_CreateAttr(UsdGeomTokens->visibility,
                       SdfValueTypeNames->Token,
                       /* custom = */ false,
                       SdfVariabilityVarying,
                       defaultValue,
                       writeSparsely);
}

UsdAttribute
UsdGeomImageable::GetPurposeAttr() const
{
    return GetPrim().GetAttribute(UsdGeomTokens->purpose);
}

UsdAttribute
UsdGeomImageable::CreatePurposeAttr(VtValue const &defaultValue, bool writeSparsely) const
{
    return UsdSchemaBase::_CreateAttr(UsdGeomTokens->purpose,
                       SdfValueTypeNames->Token,
                       /* custom = */ false,
                       SdfVariabilityUniform,
                       defaultValue,
                       writeSparsely);
}

UsdRelationship
UsdGeomImageable::GetProxyPrimRel() const
{
    return GetPrim().GetRelationship(UsdGeomTokens->proxyPrim);
}

UsdRelationship
UsdGeomImageable::CreateProxyPrimRel() const
{
    return GetPrim().CreateRelationship(UsdGeomTokens->proxyPrim,
                       /* custom = */ false);
}

namespace {
static inline TfTokenVector
_ConcatenateAttributeNames(const TfTokenVector& left,const TfTokenVector& right)
{
    TfTokenVector result;
    result.reserve(left.size() + right.size());
    result.insert(result.end(), left.begin(), left.end());
    result.insert(result.end(), right.begin(), right.end());
    return result;
}
}

/*static*/
const TfTokenVector&
UsdGeomImageable::GetSchemaAttributeNames(bool includeInherited)
{
    static TfTokenVector localNames = {
        UsdGeomTokens->visibility,
        UsdGeomTokens->purpose,
    };
    static TfTokenVector allNames =
        _ConcatenateAttributeNames(
            UsdTyped::GetSchemaAttributeNames(true),
            localNames);

    if (includeInherited)
        return allNames;
    else
        return localNames;
}

PXR_NAMESPACE_CLOSE_SCOPE

// ===================================================================== //
// Feel free to add custom code below this line. It will be preserved by
// the code generator.
//
// Just remember to wrap code in the appropriate delimiters:
// 'PXR_NAMESPACE_OPEN_SCOPE', 'PXR_NAMESPACE_CLOSE_SCOPE'.
// ===================================================================== //
// --(BEGIN CUSTOM CODE)--

#include "pxr/usd/usdGeom/bboxCache.h"
#include "pxr/usd/usdGeom/xformCache.h"
#include "pxr/usd/usdGeom/primvarsAPI.h"
#include "pxr/usd/usdGeom/visibilityAPI.h"
#include "pxr/base/tf/envSetting.h"

PXR_NAMESPACE_OPEN_SCOPE

/* static */
const TfTokenVector &
UsdGeomImageable::GetOrderedPurposeTokens()
{
    static const TfTokenVector purposeTokens = {
        UsdGeomTokens->default_,
        UsdGeomTokens->render,
        UsdGeomTokens->proxy,
        UsdGeomTokens->guide };

    return purposeTokens;
}

static
TfToken
_ComputeVisibility(UsdPrim const &prim, UsdTimeCode const &time)
{
    TfToken localVis;
    if (UsdGeomImageable ip = UsdGeomImageable(prim)) {
        ip.GetVisibilityAttr().Get(&localVis, time);

        if (localVis == UsdGeomTokens->invisible) {
            return UsdGeomTokens->invisible;
        }
    }

    if (UsdPrim parent = prim.GetParent()) {
        return _ComputeVisibility(parent, time);
    }

    return UsdGeomTokens->inherited;
}

TfToken
UsdGeomImageable::ComputeVisibility(UsdTimeCode const &time) const
{
    return _ComputeVisibility(GetPrim(), time);
}

UsdAttribute
UsdGeomImageable::GetPurposeVisibilityAttr(
    const TfToken &purpose) const
{
    if (purpose == UsdGeomTokens->default_) {
        return GetVisibilityAttr();
    }

    if (UsdGeomVisibilityAPI visAPI = UsdGeomVisibilityAPI(GetPrim())) {
        return visAPI.GetPurposeVisibilityAttr(purpose);        
    }
    return {};
}

static
TfToken
_ComputePurposeVisibility(
    const UsdPrim &prim,
    const TfToken &purpose,
    const UsdTimeCode &time)
{
    // If we find an authored purpose visibility opinion, return it.
    if (const UsdGeomImageable ip = UsdGeomImageable(prim)) {
        TfToken localVis;
        const UsdAttribute attr = ip.GetPurposeVisibilityAttr(purpose);
        if (attr && attr.HasAuthoredValue() && attr.Get(&localVis, time)) {
            return localVis;
        }
    }

    // Otherwise, we inherit purpose visibility from the parent.
    if (const UsdPrim parent = prim.GetParent()) {
        return _ComputePurposeVisibility(parent, purpose, time);
    }

    // If we don't have an authored opinion and we don't have a parent,
    // return a fallback value, depending on the purpose.
    if (purpose == UsdGeomTokens->guide) {
        return UsdGeomTokens->invisible;
    }
    if (purpose == UsdGeomTokens->proxy ||
        purpose == UsdGeomTokens->render) {
        return UsdGeomTokens->inherited;
    }

    TF_CODING_ERROR(
        "Unexpected purpose '%s' computing purpose visibility for <%s>.",
        purpose.GetText(),
        prim.GetPath().GetText());
    return UsdGeomTokens->invisible;
}

TfToken
UsdGeomImageable::ComputeEffectiveVisibility(
    const TfToken &purpose,
    UsdTimeCode const &time) const
{
    // If overall visibility is invisible, effective purpose visibility is
    // invisible.
    if (ComputeVisibility(time) == UsdGeomTokens->invisible) {
        return UsdGeomTokens->invisible;
    }
    
    // Default visibility is entirely determined by overall visibility, so
    // no need to traverse further.
    if (purpose == UsdGeomTokens->default_) {
        return UsdGeomTokens->visible;
    }

    return _ComputePurposeVisibility(GetPrim(), purpose, time);
}

static void
_SetVisibility(const UsdGeomImageable &imageable, const TfToken &visState, 
               const UsdTimeCode &time)
{
    imageable.CreateVisibilityAttr().Set(visState, time);
}

// Returns true if the imageable has its visibility set to 'invisible' at the 
// given time. It also sets the visibility to inherited before returning.
static 
bool
_SetInheritedIfInvisible(const UsdGeomImageable &imageable,
                         const UsdTimeCode &time)
{
    TfToken vis;
    if (imageable.GetVisibilityAttr().Get(&vis, time)) {
        if (vis == UsdGeomTokens->invisible) {
            _SetVisibility(imageable, UsdGeomTokens->inherited, time);
            return true;
        }
    }
    return false;
}

static
void
_MakeVisible(const UsdPrim &prim, UsdTimeCode const &time,
             bool *hasInvisibleAncestor)
{
    if (UsdPrim parent = prim.GetParent()) {
        _MakeVisible(parent, time, hasInvisibleAncestor);

        if (UsdGeomImageable imageableParent = UsdGeomImageable(parent)) {

            // Change visibility of parent to inherited if it is invisible.
            if (_SetInheritedIfInvisible(imageableParent, time) ||
                *hasInvisibleAncestor) {

                *hasInvisibleAncestor = true;

                // Invis all siblings of prim.
                for (const UsdPrim &childPrim : parent.GetAllChildren()) {
                    if (childPrim != prim) {
                        UsdGeomImageable imageableChild(childPrim);
                        if (imageableChild) {
                            _SetVisibility(imageableChild, 
                                UsdGeomTokens->invisible, time);
                        }
                    }
                }
            }
        }
    }
}

void 
UsdGeomImageable::MakeVisible(const UsdTimeCode &time) const
{
    bool hasInvisibleAncestor = false;
    _SetInheritedIfInvisible(*this, time);
    _MakeVisible(GetPrim(), time, &hasInvisibleAncestor);
}

void
UsdGeomImageable::MakeInvisible(const UsdTimeCode &time) const
{
    UsdAttribute visAttr = CreateVisibilityAttr();
    TfToken myVis;
    if (!visAttr.Get(&myVis, time) || myVis != UsdGeomTokens->invisible) {
        visAttr.Set(UsdGeomTokens->invisible, time);
    }
}

// Helper for computing only the authored purpose token from a valid imageable
// prim. Returns an empty purpose token otherwise.
static TfToken
_ComputeAuthoredPurpose(const UsdGeomImageable &ip)
{
    if (ip) {
        UsdAttribute purposeAttr = ip.GetPurposeAttr();
        if (purposeAttr.HasAuthoredValue()) {
            TfToken purpose;
            purposeAttr.Get(&purpose);
            return purpose;
        }
    }
    return TfToken();
}

// Helper for computing the fallback purpose from a valid imageable prim 
// assuming we didn't find an authored purpose. Returns the "default" purpose
// as the fallback for non-imageable prims.
static TfToken
_ComputeFallbackPurpose(const UsdGeomImageable &ip)
{
    TfToken purpose = UsdGeomTokens->default_;
    if (ip) {
        UsdAttribute purposeAttr = ip.GetPurposeAttr();
        purposeAttr.Get(&purpose);
    }
    return purpose;
}

// Helper for computing the purpose that can be inherited from an ancestor 
// imageable when there is no authored purpose on the prim. Walks up the prim
// hierarchy and returns the first authored purpose opinion found on an 
// imageable prim. Returns an empty token if there's purpose opinion to inherit
// from.
static TfToken
_ComputeInheritableAncestorPurpose(const UsdPrim &prim)
{
    UsdPrim parent = prim.GetParent();
    while (parent) {
        const TfToken purpose =
            _ComputeAuthoredPurpose(UsdGeomImageable(parent));
        if (!purpose.IsEmpty()) {
            return purpose;
        }
        parent = parent.GetParent();
    }
    return TfToken();
}

TfToken
UsdGeomImageable::ComputePurpose() const
{
    return ComputePurposeInfo().purpose;
}

UsdGeomImageable::PurposeInfo 
UsdGeomImageable::ComputePurposeInfo() const
{
    // Check for an authored purpose opinion (if we're imageable) first. If 
    // none, check for an inheritable ancestor opinion. If still none return 
    // the fallback purpose.
    TfToken authoredPurpose = _ComputeAuthoredPurpose(*this);
    if (authoredPurpose.IsEmpty()) {
        TfToken inheritableParentPurpose = 
            _ComputeInheritableAncestorPurpose(GetPrim());
        if (inheritableParentPurpose.IsEmpty()) {
            return PurposeInfo (_ComputeFallbackPurpose(*this), false);
        } else {
            return PurposeInfo (inheritableParentPurpose, true);
        }
    }
    return PurposeInfo (authoredPurpose, true);
}

UsdGeomImageable::PurposeInfo 
UsdGeomImageable::ComputePurposeInfo(const PurposeInfo &parentPurposeInfo) const
{
    // Check for an authored purpose opinion (if we're imageable) first. If 
    // none, return the passed in parent purpose if its inheritable
    // otherwise return the fallback purpose.
    TfToken authoredPurpose = _ComputeAuthoredPurpose(*this);
    if (authoredPurpose.IsEmpty()) {
        if (parentPurposeInfo.isInheritable) {
            return parentPurposeInfo;
        } else {
            return PurposeInfo (_ComputeFallbackPurpose(*this), false);
        }
    }
    return PurposeInfo (authoredPurpose, true);
}

// Helper to compute the purpose value for prim, which may or may not be
// imageable.
static
TfToken
_ComputePurpose(UsdPrim const &prim)
{
    UsdGeomImageable ip(prim);
    if (ip) {
        return ip.ComputePurpose();
    }

    return _ComputeInheritableAncestorPurpose(prim);
}

UsdPrim
UsdGeomImageable::ComputeProxyPrim(UsdPrim *renderPrim) const
{
    UsdPrim  renderRoot, self=GetPrim();

    // XXX: This may not make sense anymore now that computed purpose is no 
    // longer "pruning", i.e. you can't guarantee that all descendant prims will
    // have same purpose as the root of a subtree. Instead we now verify that 
    // this prim has the render purpose and walk up the parent chain until we
    // the last prim that still has the render purpose and treat that as the
    // render root for this prim's proxy.
    TfToken purpose = ComputePurpose();
    UsdPrim prim = GetPrim();
    while (UsdGeomImageable(prim).ComputePurpose() == UsdGeomTokens->render) {
        renderRoot = prim;
        prim = prim.GetParent();
    }

    if (renderRoot){
        SdfPathVector target;
        UsdRelationship  proxyPrimRel = 
            UsdGeomImageable(renderRoot).GetProxyPrimRel();
        if (proxyPrimRel.GetForwardedTargets(&target)){
            if (target.size() == 1){
                if (UsdPrim proxy = self.GetStage()->GetPrimAtPath(target[0])){
                    const TfToken computedPurpose = _ComputePurpose(proxy);
                    if (computedPurpose != UsdGeomTokens->proxy){
                        TF_WARN("Prim <%s>, targeted as proxyPrim of prim "
                                "<%s> should have purpose 'proxy' but has "
                                "'%s' instead.",
                                proxy.GetPath().GetText(),
                                renderRoot.GetPath().GetText(),
                                computedPurpose.GetText());
                        return UsdPrim();
                    }
                    if (renderPrim){
                        *renderPrim = renderRoot;
                    }
                    return proxy;
                }
            }
            else if (target.size() > 1){
                TF_WARN("Found multiple targets for proxyPrim rel on "
                        "prim <%s>", renderRoot.GetPath().GetText());
            }
        }
    }

    return UsdPrim();
}

bool
UsdGeomImageable::SetProxyPrim(const UsdPrim &proxy) const
{
    if (proxy){
        SdfPathVector targets {proxy.GetPath()};
        return CreateProxyPrimRel().SetTargets(targets);
    }
    return false;
}

bool
UsdGeomImageable::SetProxyPrim(const UsdSchemaBase &proxy) const
{
    if (proxy){
        SdfPathVector targets {proxy.GetPrim().GetPath()};
        return CreateProxyPrimRel().SetTargets(targets);
    }
    return false;
}


static
TfTokenVector
_MakePurposeVector(TfToken const &purpose1,
                   TfToken const &purpose2,
                   TfToken const &purpose3,
                   TfToken const &purpose4)
{
    TfTokenVector purposes;
    
    if (!purpose1.IsEmpty()) purposes.push_back(purpose1);
    if (!purpose2.IsEmpty()) purposes.push_back(purpose2);
    if (!purpose3.IsEmpty()) purposes.push_back(purpose3);
    if (!purpose4.IsEmpty()) purposes.push_back(purpose4);

    return purposes;
}

GfBBox3d
UsdGeomImageable::ComputeWorldBound(UsdTimeCode const& time,
                                    TfToken const &purpose1,
                                    TfToken const &purpose2,
                                    TfToken const &purpose3,
                                    TfToken const &purpose4) const
{
    TfTokenVector purposes = _MakePurposeVector(purpose1, purpose2,
                                                purpose3, purpose4);

    if (purposes.empty()){
        TF_CODING_ERROR("Must include at least one purpose when computing"
                        " bounds for prim at path <%s>.  See "
                        "UsdGeomImageable::GetPurposeAttr().",
                        GetPrim().GetPath().GetText());
        return GfBBox3d();
    }
    return UsdGeomBBoxCache(time, purposes).ComputeWorldBound(GetPrim());
}

GfBBox3d
UsdGeomImageable::ComputeLocalBound(UsdTimeCode const& time,
                                    TfToken const &purpose1,
                                    TfToken const &purpose2,
                                    TfToken const &purpose3,
                                    TfToken const &purpose4) const
{
    TfTokenVector purposes = _MakePurposeVector(purpose1, purpose2,
                                                purpose3, purpose4);

    if (purposes.empty()){
        TF_CODING_ERROR("Must include at least one purpose when computing"
                        " bounds for prim at path <%s>.  See "
                        "UsdGeomImageable::GetPurposeAttr().",
                        GetPrim().GetPath().GetText());
        return GfBBox3d();
    }
    return UsdGeomBBoxCache(time, purposes).ComputeLocalBound(GetPrim());
}

GfBBox3d
UsdGeomImageable::ComputeUntransformedBound(UsdTimeCode const& time,
                                            TfToken const &purpose1,
                                            TfToken const &purpose2,
                                            TfToken const &purpose3,
                                            TfToken const &purpose4) const
{
    TfTokenVector purposes = _MakePurposeVector(purpose1, purpose2,
                                                purpose3, purpose4);

    if (purposes.empty()){
        TF_CODING_ERROR("Must include at least one purpose when computing"
                        " bounds for prim at path <%s>.  See "
                        "UsdGeomImageable::GetPurposeAttr().",
                        GetPrim().GetPath().GetText());
        return GfBBox3d();
    }
    return
        UsdGeomBBoxCache(time, purposes).ComputeUntransformedBound(GetPrim());
}

GfMatrix4d
UsdGeomImageable::ComputeLocalToWorldTransform(UsdTimeCode const &time) const
{
    return UsdGeomXformCache(time).GetLocalToWorldTransform(GetPrim());
}

GfMatrix4d
UsdGeomImageable::ComputeParentToWorldTransform(UsdTimeCode const &time) const
{
    return UsdGeomXformCache(time).GetParentToWorldTransform(GetPrim());
}

PXR_NAMESPACE_CLOSE_SCOPE
