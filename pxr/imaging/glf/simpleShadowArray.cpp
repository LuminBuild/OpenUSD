//
// Copyright 2016 Pixar
//
// Licensed under the terms set forth in the LICENSE.txt file available at
// https://openusd.org/license.
//
/// \file simpleShadowArray.cpp

#include "pxr/imaging/garch/glApi.h"

#include "pxr/imaging/glf/simpleShadowArray.h"
#include "pxr/imaging/glf/debugCodes.h"
#include "pxr/imaging/glf/diagnostic.h"
#include "pxr/imaging/glf/glContext.h"
#include "pxr/imaging/hio/image.h"

#include "pxr/base/arch/fileSystem.h"
#include "pxr/base/gf/vec2i.h"
#include "pxr/base/gf/vec4d.h"
#include "pxr/base/tf/debug.h"
#include "pxr/base/tf/envSetting.h"
#include "pxr/base/tf/stringUtils.h"

#include <string>
#include <vector>


PXR_NAMESPACE_OPEN_SCOPE

GlfSimpleShadowArray::GlfSimpleShadowArray() :
    _framebuffer(0),
    _shadowDepthSampler(0),
    _shadowCompareSampler(0),
    _unbindRestoreDrawFramebuffer(0),
    _unbindRestoreReadFramebuffer(0),
    _unbindRestoreViewport{0,0,0,0},
    _texturesAllocatedExternally(false)
{
}

GlfSimpleShadowArray::~GlfSimpleShadowArray()
{
    _FreeResources();
}

GLuint
GlfSimpleShadowArray::GetShadowMapTexture(int shadowIndex) const
{
    return _textures[shadowIndex];
}
GLuint
GlfSimpleShadowArray::GetShadowMapDepthSampler() const
{
    if (!_shadowDepthSampler) {
        TF_CODING_ERROR("Shadow depth sampler has not been allocated");
    }
    return _shadowDepthSampler;
}

GLuint
GlfSimpleShadowArray::GetShadowMapCompareSampler() const
{
    if (!_shadowCompareSampler) {
        TF_CODING_ERROR("Shadow compare sampler has not been allocated");
    }
    return _shadowCompareSampler;
}

void
GlfSimpleShadowArray::SetShadowMapResolutions(
    std::vector<GfVec2i> const& resolutions)
{
    if (_resolutions == resolutions) {
        return;
    }

    _resolutions = resolutions;

    if (!_texturesAllocatedExternally) {
        _FreeTextures();
    }

    size_t numShadowMaps = _resolutions.size();
    if (_viewMatrix.size() != numShadowMaps ||
        _projectionMatrix.size() != numShadowMaps) {
        _viewMatrix.resize(numShadowMaps, GfMatrix4d().SetIdentity());
        _projectionMatrix.resize(numShadowMaps, GfMatrix4d().SetIdentity());
    }
}

size_t
GlfSimpleShadowArray::GetNumShadowMapPasses() const
{
    // we require one pass per shadow map.
    return _resolutions.size();
}

GfVec2i
GlfSimpleShadowArray::GetShadowMapSize(size_t index) const
{
    GfVec2i shadowMapSize(0);
    if (TF_VERIFY(index < _resolutions.size())) {
        shadowMapSize = _resolutions[index];
    }

    return shadowMapSize;
}

GfMatrix4d
GlfSimpleShadowArray::GetViewMatrix(size_t index) const
{
    if (!TF_VERIFY(index < _viewMatrix.size())) {
        return GfMatrix4d(1.0);
    }

    return _viewMatrix[index];
}

void
GlfSimpleShadowArray::SetViewMatrix(size_t index, GfMatrix4d const & matrix)
{
    if (!TF_VERIFY(index < _viewMatrix.size())) {
        return;
    }

    _viewMatrix[index] = matrix;
}

GfMatrix4d
GlfSimpleShadowArray::GetProjectionMatrix(size_t index) const
{
    if (!TF_VERIFY(index < _projectionMatrix.size())) {
        return GfMatrix4d(1.0);
    }

    return _projectionMatrix[index];
}

void
GlfSimpleShadowArray::SetProjectionMatrix(size_t index, GfMatrix4d const & matrix)
{
    if (!TF_VERIFY(index < _projectionMatrix.size())) {
        return;
    }

    _projectionMatrix[index] = matrix;
}

GfMatrix4d
GlfSimpleShadowArray::GetWorldToShadowMatrix(size_t index) const
{
    // Transform shadow space clip coordinates such that after the homegenous
    // divide, the resulting XYZ coordinates are in the range [0,1] and not
    // the NDC [-1,1].
    // This is used during shadow map sampling. (X,Y) serves as the texture
    // coordinate and Z is the compare value.
    // 
    GfMatrix4d size = GfMatrix4d().SetScale(GfVec3d(0.5, 0.5, 0.5));
    GfMatrix4d center = GfMatrix4d().SetTranslate(GfVec3d(0.5, 0.5, 0.5));
    return GetViewMatrix(index) * GetProjectionMatrix(index) * size * center;
}

void
GlfSimpleShadowArray::BeginCapture(size_t index, bool clear)
{
    _BindFramebuffer(index);

    if (clear) {
        glClear(GL_DEPTH_BUFFER_BIT);
    }

    // save the current viewport
    glGetIntegerv(GL_VIEWPORT, _unbindRestoreViewport);

    GfVec2i resolution = GetShadowMapSize(index);
    glViewport(0, 0, resolution[0], resolution[1]);

    // depth 1.0 means infinity (no occluders).
    // This value is also used as a border color
    glDepthRange(0, 0.99999);
    glEnable(GL_DEPTH_CLAMP);

    GLF_POST_PENDING_GL_ERRORS();
}

void
GlfSimpleShadowArray::EndCapture(size_t index)
{
    // reset to GL default, except viewport
    glDepthRange(0, 1.0);
    glDisable(GL_DEPTH_CLAMP);

    if (TfDebug::IsEnabled(GLF_DEBUG_DUMP_SHADOW_TEXTURES)) {
        HioImage::StorageSpec storage;
        GfVec2i resolution = GetShadowMapSize(index);
        storage.width = resolution[0];
        storage.height = resolution[1];
        storage.format = HioFormatFloat32;

        // In OpenGL, (0, 0) is the lower left corner.
        storage.flipped = true;

        const int numPixels = storage.width * storage.height;
        std::vector<GLfloat> pixelData(static_cast<size_t>(numPixels));
        storage.data = static_cast<void*>(pixelData.data());

        glReadPixels(0,
                     0,
                     storage.width,
                     storage.height,
                     GL_DEPTH_COMPONENT,
                     GL_FLOAT,
                     storage.data);

        GLfloat minValue = std::numeric_limits<float>::max();
        GLfloat maxValue = -std::numeric_limits<float>::max();
        for (int i = 0; i < numPixels; ++i) {
            const GLfloat pixelValue = pixelData[i];
            if (pixelValue < minValue) {
                minValue = pixelValue;
            }
            if (pixelValue > maxValue) {
                maxValue = pixelValue;
            }
        }

        // Remap the pixel data so that the furthest depth sample is white and
        // the nearest depth sample is black.
        for (int i = 0; i < numPixels; ++i) {
            pixelData[i] = (pixelData[i] - minValue) / (maxValue - minValue);
        }

        const std::string outputImageFile = ArchNormPath(
            TfStringPrintf("%s/GlfSimpleShadowArray.index_%zu.tif",
                           ArchGetTmpDir(),
                           index));
        HioImageSharedPtr image = HioImage::OpenForWriting(outputImageFile);
        if (image->Write(storage)) {
            TfDebug::Helper().Msg(
                "Wrote shadow texture: %s\n", outputImageFile.c_str());
        } else {
            TfDebug::Helper().Msg(
                "Failed to write shadow texture: %s\n", outputImageFile.c_str()
            );
        }
    }

    _UnbindFramebuffer();

    // restore viewport
    glViewport(_unbindRestoreViewport[0],
               _unbindRestoreViewport[1],
               _unbindRestoreViewport[2],
               _unbindRestoreViewport[3]);

    GLF_POST_PENDING_GL_ERRORS();
}

// --------- private helpers ----------
bool
GlfSimpleShadowArray::_ShadowMapExists() const
{
    return !_textures.empty();
}

void
GlfSimpleShadowArray::AllocSamplers()
{
    // Samplers
    GLfloat border[] = {1, 1, 1, 1};

    if (!_shadowDepthSampler) {
        glGenSamplers(1, &_shadowDepthSampler);
        glSamplerParameteri(
            _shadowDepthSampler, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glSamplerParameteri(
            _shadowDepthSampler, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glSamplerParameteri(
            _shadowDepthSampler, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
        glSamplerParameteri(
            _shadowDepthSampler, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
        glSamplerParameterfv(
            _shadowDepthSampler, GL_TEXTURE_BORDER_COLOR, border);
    }

    if (!_shadowCompareSampler) {
        glGenSamplers(1, &_shadowCompareSampler);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
        glSamplerParameterfv(
            _shadowCompareSampler, GL_TEXTURE_BORDER_COLOR, border);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_COMPARE_MODE, 
            GL_COMPARE_REF_TO_TEXTURE);
        glSamplerParameteri(
            _shadowCompareSampler, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL );
    }
}

void
GlfSimpleShadowArray::_AllocResources()
{
    // Samplers
    AllocSamplers();

    // Shadow maps
    if (!_texturesAllocatedExternally) {
        _AllocTextures();
    }

    // Framebuffer
    if (!_framebuffer) {
        glGenFramebuffers(1, &_framebuffer);
    }
}

void
GlfSimpleShadowArray::SetTextures(std::vector<GLuint> textureIds)
{
    _textures = textureIds;
    _texturesAllocatedExternally = !textureIds.empty();
}

void
GlfSimpleShadowArray::_AllocTextures()
{
    if (!TF_VERIFY(_shadowDepthSampler) ||
        !TF_VERIFY(_shadowCompareSampler) ||
        !TF_VERIFY(_textures.empty())) {
        TF_CODING_ERROR("Unexpected entry state in %s\n",
                        TF_FUNC_NAME().c_str());
        return;
    }

    GlfSharedGLContextScopeHolder sharedContextScopeHolder;

    // XXX: Currently, we allocate/reallocate ALL shadow maps each time.
    for (GfVec2i const& size : _resolutions) {
        GLuint id;
        glGenTextures(1, &id);
        glBindTexture(GL_TEXTURE_2D, id);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32F,
            size[0], size[1], 0, GL_DEPTH_COMPONENT, GL_FLOAT, NULL);
        _textures.push_back(id);

        TF_DEBUG(GLF_DEBUG_SHADOW_TEXTURES).Msg(
            "Created shadow map texture of size %dx%d "
            "(id %#x)\n" , size[0], size[1], id);
    }

    glBindTexture(GL_TEXTURE_2D, 0);
    _texturesAllocatedExternally = false;
}

void
GlfSimpleShadowArray::_FreeResources()
{
    GlfSharedGLContextScopeHolder sharedContextScopeHolder;

    if (!_texturesAllocatedExternally) {
        _FreeTextures();
    }

    if (_framebuffer) {
        glDeleteFramebuffers(1, &_framebuffer);
        _framebuffer = 0;
    }
    if (_shadowDepthSampler) {
        glDeleteSamplers(1, &_shadowDepthSampler);
        _shadowDepthSampler = 0;
    }
    if (_shadowCompareSampler) {
        glDeleteSamplers(1, &_shadowCompareSampler);
        _shadowCompareSampler = 0;
    }
}

void
GlfSimpleShadowArray::_FreeTextures()
{
    if (!_textures.empty()) {
        GlfSharedGLContextScopeHolder sharedContextScopeHolder;
        // XXX: Ideally, we don't deallocate all textures, and only those that
        // have resolution modified.

        for (GLuint const& id : _textures) {
            if (id) {
                glDeleteTextures(1, &id);
            }
        }
        _textures.clear();
        
        GLF_POST_PENDING_GL_ERRORS();
    }
}

void
GlfSimpleShadowArray::_BindFramebuffer(size_t index)
{
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,
                  (GLint*)&_unbindRestoreDrawFramebuffer);
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING,
                  (GLint*)&_unbindRestoreReadFramebuffer);

    if (!_framebuffer || !_ShadowMapExists()) {
        _AllocResources();
    }

    glBindFramebuffer(GL_FRAMEBUFFER, _framebuffer);

    if (index < _textures.size()) {
        glFramebufferTexture(GL_FRAMEBUFFER,
            GL_DEPTH_ATTACHMENT, _textures[index], 0);
    } else {
        TF_CODING_WARNING("Texture index is out of bounds");
    }

    GLF_POST_PENDING_GL_ERRORS();
}

void
GlfSimpleShadowArray::_UnbindFramebuffer()
{
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, _unbindRestoreDrawFramebuffer);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, _unbindRestoreReadFramebuffer);

    GLF_POST_PENDING_GL_ERRORS();
}


PXR_NAMESPACE_CLOSE_SCOPE
