//
// Copyright 2016 Pixar
//
// Licensed under the terms set forth in the LICENSE.txt file available at
// https://openusd.org/license.
//
#include "pxr/usd/usdRi/splineAPI.h"
#include "pxr/usd/usd/schemaRegistry.h"
#include "pxr/usd/usd/typed.h"

#include "pxr/usd/sdf/types.h"
#include "pxr/usd/sdf/assetPath.h"

PXR_NAMESPACE_OPEN_SCOPE

// Register the schema with the TfType system.
TF_REGISTRY_FUNCTION(TfType)
{
    TfType::Define<UsdRiSplineAPI,
        TfType::Bases< UsdAPISchemaBase > >();
    
}

/* virtual */
UsdRiSplineAPI::~UsdRiSplineAPI()
{
}

/* static */
UsdRiSplineAPI
UsdRiSplineAPI::Get(const UsdStagePtr &stage, const SdfPath &path)
{
    if (!stage) {
        TF_CODING_ERROR("Invalid stage");
        return UsdRiSplineAPI();
    }
    return UsdRiSplineAPI(stage->GetPrimAtPath(path));
}


/* virtual */
UsdSchemaKind UsdRiSplineAPI::_GetSchemaKind() const
{
    return UsdRiSplineAPI::schemaKind;
}

/* static */
bool
UsdRiSplineAPI::CanApply(
    const UsdPrim &prim, std::string *whyNot)
{
    return prim.CanApplyAPI<UsdRiSplineAPI>(whyNot);
}

/* static */
UsdRiSplineAPI
UsdRiSplineAPI::Apply(const UsdPrim &prim)
{
    if (prim.ApplyAPI<UsdRiSplineAPI>()) {
        return UsdRiSplineAPI(prim);
    }
    return UsdRiSplineAPI();
}

/* static */
const TfType &
UsdRiSplineAPI::_GetStaticTfType()
{
    static TfType tfType = TfType::Find<UsdRiSplineAPI>();
    return tfType;
}

/* static */
bool 
UsdRiSplineAPI::_IsTypedSchema()
{
    static bool isTyped = _GetStaticTfType().IsA<UsdTyped>();
    return isTyped;
}

/* virtual */
const TfType &
UsdRiSplineAPI::_GetTfType() const
{
    return _GetStaticTfType();
}

/*static*/
const TfTokenVector&
UsdRiSplineAPI::GetSchemaAttributeNames(bool includeInherited)
{
    static TfTokenVector localNames;
    static TfTokenVector allNames =
        UsdAPISchemaBase::GetSchemaAttributeNames(true);

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

#include "pxr/usd/usdRi/tokens.h"
#include <algorithm>

PXR_NAMESPACE_OPEN_SCOPE

TfToken 
UsdRiSplineAPI::_GetScopedPropertyName(const TfToken &baseName) const
{
    return TfToken(
        SdfPath::JoinIdentifier(
            SdfPath::JoinIdentifier(
                _splineName.GetString(),
                UsdRiTokens->spline.GetString()),
            baseName.GetString()));
}

UsdAttribute
UsdRiSplineAPI::GetInterpolationAttr() const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->interpolation);
    return GetPrim().GetAttribute(name);
}

UsdAttribute
UsdRiSplineAPI::CreateInterpolationAttr(VtValue const &defaultValue, bool writeSparsely) const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->interpolation);
    return UsdSchemaBase::_CreateAttr(name,
                       SdfValueTypeNames->Token,
                       /* custom = */ false,
                       SdfVariabilityUniform,
                       defaultValue,
                       writeSparsely);
}

UsdAttribute
UsdRiSplineAPI::GetPositionsAttr() const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->positions);
    return GetPrim().GetAttribute(name);
}

UsdAttribute
UsdRiSplineAPI::CreatePositionsAttr(VtValue const &defaultValue, bool writeSparsely) const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->positions);
    return UsdSchemaBase::_CreateAttr(name,
                       SdfValueTypeNames->FloatArray,
                       /* custom = */ false,
                       SdfVariabilityUniform,
                       defaultValue,
                       writeSparsely);
}

UsdAttribute
UsdRiSplineAPI::GetValuesAttr() const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->values);
    return GetPrim().GetAttribute(name);
}

UsdAttribute
UsdRiSplineAPI::CreateValuesAttr(VtValue const &defaultValue, bool writeSparsely) const
{
    TfToken name = _GetScopedPropertyName(UsdRiTokens->values);
    return UsdSchemaBase::_CreateAttr(name,
                       _valuesTypeName,
                       /* custom = */ false,
                       SdfVariabilityUniform,
                       defaultValue,
                       writeSparsely);
}

bool 
UsdRiSplineAPI::Validate(std::string *reason) const
{
    if (_splineName.IsEmpty()) {
        *reason += "SplineAPI is not correctly initialized";
        return false;
    }

    UsdAttribute interpAttr = GetInterpolationAttr();
    UsdAttribute posAttr = GetPositionsAttr();
    UsdAttribute valAttr = GetValuesAttr();

    if (_valuesTypeName != SdfValueTypeNames->FloatArray &&
        _valuesTypeName != SdfValueTypeNames->Color3fArray) {
        *reason += "SplineAPI is configured for an unsupported value type '" +
            _valuesTypeName.GetAsToken().GetString() + "'";
        return false;
    }
    if (!interpAttr) {
        *reason += "Could not get the interpolation attribute.";
        return false;
    }
    if (!posAttr) {
        *reason += "Could not get the position attribute.";
        return false;
    }
    TfToken interp;
    interpAttr.Get(&interp);
    if (interp != UsdRiTokens->constant &&
        interp != UsdRiTokens->linear &&
        interp != UsdRiTokens->catmullRom &&
        interp != UsdRiTokens->bspline) {
        *reason += "Interpolation attribute has invalid value '" +
            interp.GetString() + "'";
        return false;
    }
    if (posAttr.GetTypeName() != SdfValueTypeNames->FloatArray) {
        *reason += "Values attribute has incorrect type; found '" +
            valAttr.GetTypeName().GetAsToken().GetString() +
            "' but expected '" +
            SdfValueTypeNames->FloatArray.GetAsToken().GetString() +
            "'";
        return false;
    }
    VtFloatArray positions;
    posAttr.Get(&positions);
    if (!std::is_sorted(positions.begin(), positions.end())) {
        *reason += "Positions attribute must be sorted in increasing order";
        return false;
    }
    if (valAttr.GetTypeName() != _valuesTypeName) {
        *reason += "Values attribute has incorrect type; found '" +
            valAttr.GetTypeName().GetAsToken().GetString() +
            "' but expected '" +
            _valuesTypeName.GetAsToken().GetString() +
            "'";
        return false;
    }
    size_t numValues = 0;
    if (_valuesTypeName == SdfValueTypeNames->FloatArray) {
        VtFloatArray vals;
        valAttr.Get(&vals);
        numValues = vals.size();
    } else if (_valuesTypeName == SdfValueTypeNames->Color3fArray) {
        VtVec3fArray vals;
        valAttr.Get(&vals);
        numValues = vals.size();
    }
    if (positions.size() != numValues) {
        *reason += "Values attribute and positions attribute must " \
                    "have the same number of entries";
        return false;
    }

    return true;
}

PXR_NAMESPACE_CLOSE_SCOPE
