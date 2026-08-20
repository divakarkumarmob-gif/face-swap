document.addEventListener('DOMContentLoaded', () => {
    // Current Active Mode ('photo' | 'video' | 'live-record' | 'video-call')
    let currentMode = 'photo';

    // Application State
    const state = {
        // Photo Mode State
        photo: {
            sourceFile: null,
            sourceFiles: [],
            sourceTemplate: null,
            targetFile: null,
            targetTemplate: null
        },
        // Video Mode State
        video: {
            sourceFile: null,
            sourceFiles: [],
            sourceTemplate: null,
            targetFile: null,
            targetTemplate: null,
            selectedPersonId: null,
            selectedPersonEmbedding: null,
            detectedPeople: []
        },
        // Live Camera & Recording State
        live: {
            sourceFile: null,
            sourceFiles: [],
            sourceTemplate: null,
            sourceId: null,
            stream: null,
            isCameraOn: false,
            isSwapping: true,
            isMirrored: true,
            isRecording: false,
            isPaused: false,
            mediaRecorder: null,
            recordedChunks: [],
            recordStartTime: 0,
            recordTimerInterval: null,
            recordElapsedMs: 0,
            recordPauseStart: 0,
            ws: null,
            isProcessingFrame: false,
            fps: 0,
            frameCount: 0,
            lastFpsTime: performance.now(),
            latency: 0,
            activeAnimationId: null
        },
        // Video Call State
        call: {
            roomId: null,
            clientId: 'peer_' + Math.random().toString(36).substring(2, 9),
            ws: null,
            peerConnection: null,
            localStream: null,
            remoteStream: null,
            isMicOn: true,
            isCamOn: true,
            isSwapOn: true,
            isScreenSharing: false,
            screenStream: null,
            sourceId: null,
            activeAvatarPreset: null,
            isCallRecording: false,
            callRecorder: null,
            callRecordedChunks: []
        },
        currentJobId: null,
        pollInterval: null
    };

    // DOM Elements - Mode Switcher
    const tabPhoto = document.getElementById('tabPhoto');
    const tabVideo = document.getElementById('tabVideo');
    const tabLiveRecord = document.getElementById('tabLiveRecord');
    const tabVideoCall = document.getElementById('tabVideoCall');

    const photoModeContainer = document.getElementById('photoModeContainer');
    const videoModeContainer = document.getElementById('videoModeContainer');
    const liveRecordContainer = document.getElementById('liveRecordContainer');
    const videoCallContainer = document.getElementById('videoCallContainer');

    // DOM Elements - Photo Mode
    const photoSourceDropzone = document.getElementById('photoSourceDropzone');
    const photoSourceFileInput = document.getElementById('photoSourceFileInput');
    const photoSourceEmptyState = document.getElementById('photoSourceEmptyState');
    const photoSourcePreviewState = document.getElementById('photoSourcePreviewState');
    const photoSourcePreviewImg = document.getElementById('photoSourcePreviewImg');
    const photoSourceFusionBadge = document.getElementById('photoSourceFusionBadge');
    const photoMultiGallery = document.getElementById('photoMultiGallery');
    const photoCountBadge = document.getElementById('photoCountBadge');
    const btnAddMorePhotoSource = document.getElementById('btnAddMorePhotoSource');
    const photoMultiThumbnails = document.getElementById('photoMultiThumbnails');
    const btnBrowsePhotoSource = document.getElementById('btnBrowsePhotoSource');
    const btnRemovePhotoSource = document.getElementById('btnRemovePhotoSource');
    const photoSourcePresetsRow = document.getElementById('photoSourcePresetsRow');

    const photoTargetDropzone = document.getElementById('photoTargetDropzone');
    const photoTargetFileInput = document.getElementById('photoTargetFileInput');
    const photoTargetEmptyState = document.getElementById('photoTargetEmptyState');
    const photoTargetPreviewState = document.getElementById('photoTargetPreviewState');
    const photoTargetPreviewImg = document.getElementById('photoTargetPreviewImg');
    const btnBrowsePhotoTarget = document.getElementById('btnBrowsePhotoTarget');
    const btnRemovePhotoTarget = document.getElementById('btnRemovePhotoTarget');
    const photoTargetPresetsRow = document.getElementById('photoTargetPresetsRow');

    const togglePhotoEnhancer = document.getElementById('togglePhotoEnhancer');
    const togglePhotoGrain = document.getElementById('togglePhotoGrain');
    const btnStartPhotoSwap = document.getElementById('btnStartPhotoSwap');

    // DOM Elements - Video Mode
    const videoSourceDropzone = document.getElementById('videoSourceDropzone');
    const videoSourceFileInput = document.getElementById('videoSourceFileInput');
    const videoSourceEmptyState = document.getElementById('videoSourceEmptyState');
    const videoSourcePreviewState = document.getElementById('videoSourcePreviewState');
    const videoSourcePreviewImg = document.getElementById('videoSourcePreviewImg');
    const videoSourceFusionBadge = document.getElementById('videoSourceFusionBadge');
    const videoMultiGallery = document.getElementById('videoMultiGallery');
    const videoCountBadge = document.getElementById('videoCountBadge');
    const btnAddMoreVideoSource = document.getElementById('btnAddMoreVideoSource');
    const videoMultiThumbnails = document.getElementById('videoMultiThumbnails');
    const btnBrowseVideoSource = document.getElementById('btnBrowseVideoSource');
    const btnRemoveVideoSource = document.getElementById('btnRemoveVideoSource');
    const videoSourcePresetsRow = document.getElementById('videoSourcePresetsRow');

    const videoTargetDropzone = document.getElementById('videoTargetDropzone');
    const videoTargetFileInput = document.getElementById('videoTargetFileInput');
    const videoTargetEmptyState = document.getElementById('videoTargetEmptyState');
    const videoTargetPreviewState = document.getElementById('videoTargetPreviewState');
    const videoTargetPreviewVideo = document.getElementById('videoTargetPreviewVideo');
    const videoDurationBadge = document.getElementById('videoDurationBadge');
    const btnBrowseVideoTarget = document.getElementById('btnBrowseVideoTarget');
    const btnRemoveVideoTarget = document.getElementById('btnRemoveVideoTarget');
    const videoPresetsRow = document.getElementById('videoPresetsRow');

    const targetPeopleSection = document.getElementById('targetPeopleSection');
    const peopleDetectedCount = document.getElementById('peopleDetectedCount');
    const peopleChipsContainer = document.getElementById('peopleChipsContainer');

    const durationSelect = document.getElementById('durationSelect');
    const toggleVideoEnhancer = document.getElementById('toggleVideoEnhancer');
    const toggleVideoSmoothing = document.getElementById('toggleVideoSmoothing');
    const toggleVideoGrain = document.getElementById('toggleVideoGrain');
    const btnStartVideoSwap = document.getElementById('btnStartVideoSwap');

    // DOM Elements - Live Camera & Recording
    const liveSourceDropzone = document.getElementById('liveSourceDropzone');
    const liveSourceFileInput = document.getElementById('liveSourceFileInput');
    const liveSourceEmptyState = document.getElementById('liveSourceEmptyState');
    const liveSourcePreviewState = document.getElementById('liveSourcePreviewState');
    const liveSourcePreviewImg = document.getElementById('liveSourcePreviewImg');
    const liveSourceFusionBadge = document.getElementById('liveSourceFusionBadge');
    const liveMultiGallery = document.getElementById('liveMultiGallery');
    const liveCountBadge = document.getElementById('liveCountBadge');
    const btnAddMoreLiveSource = document.getElementById('btnAddMoreLiveSource');
    const liveMultiThumbnails = document.getElementById('liveMultiThumbnails');
    const btnBrowseLiveSource = document.getElementById('btnBrowseLiveSource');
    const btnRemoveLiveSource = document.getElementById('btnRemoveLiveSource');
    const liveSourcePresetsRow = document.getElementById('liveSourcePresetsRow');

    const liveWebcamVideo = document.getElementById('liveWebcamVideo');
    const liveSwapCanvas = document.getElementById('liveSwapCanvas');
    const liveCamPlaceholder = document.getElementById('liveCamPlaceholder');
    const btnStartCamFromPlaceholder = document.getElementById('btnStartCamFromPlaceholder');
    const liveStatusHud = document.getElementById('liveStatusHud');
    const liveStatusText = document.getElementById('liveStatusText');
    const liveFpsBadge = document.getElementById('liveFpsBadge');
    const liveFpsVal = document.getElementById('liveFpsVal');
    const liveLatencyBadge = document.getElementById('liveLatencyBadge');
    const liveLatencyVal = document.getElementById('liveLatencyVal');
    const liveFaceStatusBadge = document.getElementById('liveFaceStatusBadge');
    const liveFaceStatusText = document.getElementById('liveFaceStatusText');
    const liveRecordingTimerPill = document.getElementById('liveRecordingTimerPill');
    const liveRecordDurationText = document.getElementById('liveRecordDurationText');

    const btnFlipCamera = document.getElementById('btnFlipCamera');
    const btnSnapshotQuick = document.getElementById('btnSnapshotQuick');
    const btnToggleLiveSwapOnCanvas = document.getElementById('btnToggleLiveSwapOnCanvas');
    const toggleLiveFastMode = document.getElementById('toggleLiveFastMode');
    const toggleLiveEnhancer = document.getElementById('toggleLiveEnhancer');
    const liveResolutionSelect = document.getElementById('liveResolutionSelect');

    const btnToggleCamera = document.getElementById('btnToggleCamera');
    const btnToggleCameraText = document.getElementById('btnToggleCameraText');
    const btnStartRecording = document.getElementById('btnStartRecording');
    const btnRecordText = document.getElementById('btnRecordText');
    const btnPauseRecording = document.getElementById('btnPauseRecording');
    const btnPauseText = document.getElementById('btnPauseText');
    const btnTakeLiveSnapshot = document.getElementById('btnTakeLiveSnapshot');

    const liveRecordResultCard = document.getElementById('liveRecordResultCard');
    const recordedDurationBadge = document.getElementById('recordedDurationBadge');
    const liveRecordedVideoPlayer = document.getElementById('liveRecordedVideoPlayer');
    const btnDownloadRecordedVideo = document.getElementById('btnDownloadRecordedVideo');
    const btnCloseRecordedResult = document.getElementById('btnCloseRecordedResult');

    // DOM Elements - AI Video Call
    const btnCreateCallRoom = document.getElementById('btnCreateCallRoom');
    const callRoomInput = document.getElementById('callRoomInput');
    const btnJoinCallRoom = document.getElementById('btnJoinCallRoom');
    const btnCopyCallLink = document.getElementById('btnCopyCallLink');
    const copyLinkText = document.getElementById('copyLinkText');
    const callStatusIndicator = document.getElementById('callStatusIndicator');
    const callStatusText = document.getElementById('callStatusText');

    const callLocalWebcamVideo = document.getElementById('callLocalWebcamVideo');
    const callLocalCanvas = document.getElementById('callLocalCanvas');
    const localCamOffOverlay = document.getElementById('localCamOffOverlay');
    const callLocalFpsVal = document.getElementById('callLocalFpsVal');
    const localSwapTag = document.getElementById('localSwapTag');
    const callFaceAvatarsRow = document.getElementById('callFaceAvatarsRow');
    const btnUploadCustomCallFace = document.getElementById('btnUploadCustomCallFace');
    const callCustomFaceInput = document.getElementById('callCustomFaceInput');

    const callRemoteVideo = document.getElementById('callRemoteVideo');
    const remoteWaitingOverlay = document.getElementById('remoteWaitingOverlay');
    const callRoomCodeDisplay = document.getElementById('callRoomCodeDisplay');
    const btnShareCallCodeQuick = document.getElementById('btnShareCallCodeQuick');
    const remoteLivePill = document.getElementById('remoteLivePill');

    const btnToggleCallMic = document.getElementById('btnToggleCallMic');
    const btnToggleCallCam = document.getElementById('btnToggleCallCam');
    const btnToggleCallSwap = document.getElementById('btnToggleCallSwap');
    const btnToggleCallScreenShare = document.getElementById('btnToggleCallScreenShare');
    const btnToggleCallRecording = document.getElementById('btnToggleCallRecording');
    const btnEndCall = document.getElementById('btnEndCall');

    // DOM Elements - Modal & Results
    const progressModal = document.getElementById('progressModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalStatusText = document.getElementById('modalStatusText');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressPercent = document.getElementById('progressPercent');
    const progressFrames = document.getElementById('progressFrames');
    const progressEta = document.getElementById('progressEta');

    const btnModalMinimize = document.getElementById('btnModalMinimize');
    const btnModalClose = document.getElementById('btnModalClose');
    const btnInlineMinimize = document.getElementById('btnInlineMinimize');

    const floatingProgressWidget = document.getElementById('floatingProgressWidget');
    const floatingBodyClickable = document.getElementById('floatingBodyClickable');
    const floatingTitle = document.getElementById('floatingTitle');
    const floatingPercent = document.getElementById('floatingPercent');
    const floatingBarFill = document.getElementById('floatingBarFill');
    const floatingFrames = document.getElementById('floatingFrames');
    const floatingEta = document.getElementById('floatingEta');
    const btnFloatingExpand = document.getElementById('btnFloatingExpand');
    const btnFloatingCancel = document.getElementById('btnFloatingCancel');

    const resultsSection = document.getElementById('resultsSection');
    const resultsTitle = document.getElementById('resultsTitle');
    const resultsSubtitle = document.getElementById('resultsSubtitle');
    const swappedPhotoResult = document.getElementById('swappedPhotoResult');
    const swappedVideoPlayer = document.getElementById('swappedVideoPlayer');
    const originalPhotoResult = document.getElementById('originalPhotoResult');
    const originalVideoPlayer = document.getElementById('originalVideoPlayer');
    const btnDownloadMedia = document.getElementById('btnDownloadMedia');
    const downloadBtnText = document.getElementById('downloadBtnText');
    const btnNewSwap = document.getElementById('btnNewSwap');
    const engineStatusPill = document.getElementById('engineStatusPill');
    const engineStatusText = document.getElementById('engineStatusText');

    // Tab Switching
    function setMode(mode) {
        currentMode = mode;
        [tabPhoto, tabVideo, tabLiveRecord, tabVideoCall].forEach(t => t && t.classList.remove('active'));
        [photoModeContainer, videoModeContainer, liveRecordContainer, videoCallContainer].forEach(c => c && c.classList.add('hidden'));

        if (mode === 'photo') {
            tabPhoto.classList.add('active');
            photoModeContainer.classList.remove('hidden');
        } else if (mode === 'video') {
            tabVideo.classList.add('active');
            videoModeContainer.classList.remove('hidden');
        } else if (mode === 'live-record') {
            tabLiveRecord.classList.add('active');
            liveRecordContainer.classList.remove('hidden');
        } else if (mode === 'video-call') {
            tabVideoCall.classList.add('active');
            videoCallContainer.classList.remove('hidden');
        }
    }

    tabPhoto.addEventListener('click', () => setMode('photo'));
    tabVideo.addEventListener('click', () => setMode('video'));
    if (tabLiveRecord) tabLiveRecord.addEventListener('click', () => setMode('live-record'));
    if (tabVideoCall) tabVideoCall.addEventListener('click', () => setMode('video-call'));

    // =========================================================================
    // Backend Status Check
    // =========================================================================
    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            if (res.ok) {
                const data = await res.json();
                if (data.gfpgan_loaded && data.inswapper_loaded) {
                    engineStatusText.innerHTML = `<i class="fa-solid fa-circle-check" style="color:#10b981;margin-right:4px;"></i> GFPGAN 1.4 HD Active`;
                } else if (data.initialized) {
                    engineStatusText.textContent = "AI Engine Ready";
                } else {
                    engineStatusText.textContent = "AI Engine Starting...";
                }
            }
        } catch (e) {
            engineStatusText.textContent = "Server Offline";
        }
    }
    checkStatus();

    // =========================================================================
    // Load Presets & Samples
    // =========================================================================
    async function loadTemplates() {
        try {
            const res = await fetch('/api/templates');
            if (!res.ok) return;
            const data = await res.json();

            // Populate Photo Source, Video Source, Live Source, and Call Presets
            if (data.faces && data.faces.length > 0) {
                renderFacePresets(data.faces, photoSourcePresetsRow, (face, thumb) => {
                    selectPhotoSourcePreset(face, thumb);
                });
                renderFacePresets(data.faces, videoSourcePresetsRow, (face, thumb) => {
                    selectVideoSourcePreset(face, thumb);
                });
                if (liveSourcePresetsRow) {
                    renderFacePresets(data.faces, liveSourcePresetsRow, (face, thumb) => {
                        selectLiveSourcePreset(face, thumb);
                    });
                }
                if (callFaceAvatarsRow) {
                    renderCallFaceAvatars(data.faces, callFaceAvatarsRow, (face, thumb) => {
                        selectCallFacePreset(face, thumb);
                    });
                }
            }

            // Populate Photo Target Presets
            if (data.target_photos && data.target_photos.length > 0) {
                renderFacePresets(data.target_photos, photoTargetPresetsRow, (tgt, thumb) => {
                    selectPhotoTargetPreset(tgt, thumb);
                });
            } else if (data.targets && data.targets.length > 0) {
                renderFacePresets(data.targets, photoTargetPresetsRow, (tgt, thumb) => {
                    selectPhotoTargetPreset(tgt, thumb);
                });
            }

            // Populate Video Target Presets
            if (data.videos && data.videos.length > 0) {
                renderVideoPresets(data.videos, videoPresetsRow, (vid, thumb) => {
                    selectVideoPreset(vid, thumb);
                });
            }

        } catch (e) {
            console.error("Failed to load sample templates", e);
        }
    }

    function renderFacePresets(items, container, onSelect) {
        if (!container) return;
        container.innerHTML = '';
        items.forEach(item => {
            const thumb = document.createElement('div');
            thumb.className = 'preset-thumb';
            thumb.title = item.title || item.name || item.id;
            thumb.innerHTML = `<img src="${item.url}" alt="${item.title || item.name || 'Face'}">`;
            thumb.addEventListener('click', () => onSelect(item, thumb));
            container.appendChild(thumb);
        });
    }

    function renderCallFaceAvatars(items, container, onSelect) {
        if (!container) return;
        container.innerHTML = '';
        items.forEach((item, idx) => {
            const avatar = document.createElement('div');
            avatar.className = 'call-face-avatar-item' + (idx === 0 ? ' active' : '');
            avatar.title = item.title || item.name || item.id;
            avatar.innerHTML = `<img src="${item.url}" alt="${item.title || item.name}">`;
            avatar.addEventListener('click', () => onSelect(item, avatar));
            container.appendChild(avatar);
        });
    }

    function renderVideoPresets(items, container, onSelect) {
        if (!container) return;
        container.innerHTML = '';
        items.forEach(item => {
            const thumb = document.createElement('div');
            thumb.className = 'preset-thumb video-preset-thumb';
            thumb.title = item.title || item.name || item.id;
            thumb.innerHTML = `
                <img src="${item.thumbnail || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'}" alt="${item.title || item.name}">
                <i class="fa-solid fa-play preset-play-icon"></i>
            `;
            thumb.addEventListener('click', () => onSelect(item, thumb));
            container.appendChild(thumb);
        });
    }

    loadTemplates();

    // =========================================================================
    // MULTI-PHOTO SOURCE LOGIC (PHOTO MODE)
    // =========================================================================
    let activePhotoIndex = 0;

    function selectPhotoSourcePreset(face, el) {
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.photo.sourceFile = null;
        state.photo.sourceFiles = [];
        state.photo.sourceTemplate = face.id;

        photoSourcePreviewImg.src = face.url;
        photoSourceEmptyState.classList.add('hidden');
        photoSourcePreviewState.classList.remove('hidden');
        if (photoMultiGallery) photoMultiGallery.classList.add('hidden');
        photoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-check-circle"></i> Preset Face Loaded`;
    }

    function addPhotoSourceFiles(newFilesList) {
        const valid = Array.from(newFilesList).filter(f => f.type.startsWith('image/'));
        if (!valid.length) {
            alert('Please select valid image file(s) (JPG, PNG, WEBP).');
            return;
        }

        for (let f of valid) {
            if (state.photo.sourceFiles.length < 4) {
                state.photo.sourceFiles.push(f);
            }
        }

        state.photo.sourceFile = state.photo.sourceFiles[0] || null;
        state.photo.sourceTemplate = null;
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        activePhotoIndex = state.photo.sourceFiles.length - 1;
        renderPhotoMultiGallery();
    }

    function removePhotoSourceFile(index) {
        state.photo.sourceFiles.splice(index, 1);
        if (state.photo.sourceFiles.length === 0) {
            clearPhotoSource();
        } else {
            if (activePhotoIndex >= state.photo.sourceFiles.length) {
                activePhotoIndex = state.photo.sourceFiles.length - 1;
            }
            state.photo.sourceFile = state.photo.sourceFiles[0];
            renderPhotoMultiGallery();
        }
    }

    function clearPhotoSource() {
        state.photo.sourceFile = null;
        state.photo.sourceFiles = [];
        state.photo.sourceTemplate = null;
        activePhotoIndex = 0;
        photoSourceFileInput.value = '';
        photoSourcePreviewImg.src = '';
        photoSourcePreviewState.classList.add('hidden');
        if (photoMultiGallery) photoMultiGallery.classList.add('hidden');
        photoSourceEmptyState.classList.remove('hidden');
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    }

    function renderPhotoMultiGallery() {
        const files = state.photo.sourceFiles;
        if (files.length === 0) {
            clearPhotoSource();
            return;
        }

        photoSourceEmptyState.classList.add('hidden');
        photoSourcePreviewState.classList.remove('hidden');
        if (photoMultiGallery) photoMultiGallery.classList.remove('hidden');

        // Update primary preview with selected active file
        const activeFile = files[activePhotoIndex] || files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            photoSourcePreviewImg.src = e.target.result;
        };
        reader.readAsDataURL(activeFile);

        // Update badges
        if (photoCountBadge) photoCountBadge.textContent = files.length;
        if (files.length > 1) {
            photoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-dna"></i> 3D Master Fusion (${files.length} Photos)`;
        } else {
            photoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-check-circle"></i> Input Face Loaded`;
        }

        // Render thumbnails grid
        if (photoMultiThumbnails) {
            photoMultiThumbnails.innerHTML = '';
            const angleLabels = ["P1 Front", "P2 Left", "P3 Right", "P4 Smile"];

            files.forEach((file, idx) => {
                const card = document.createElement('div');
                card.className = `gallery-thumb-card ${idx === activePhotoIndex ? 'active' : ''}`;
                card.title = `Photo ${idx + 1}: ${file.name} (Click to preview)`;

                const r = new FileReader();
                r.onload = (e) => {
                    card.innerHTML = `
                        <img src="${e.target.result}" alt="Photo ${idx + 1}">
                        <span class="gallery-thumb-badge">${angleLabels[idx] || `P${idx + 1}`}</span>
                        <button type="button" class="gallery-thumb-delete" title="Delete Photo ${idx + 1}"><i class="fa-solid fa-xmark"></i></button>
                    `;
                    card.querySelector('.gallery-thumb-delete').addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        removePhotoSourceFile(idx);
                    });
                };
                r.readAsDataURL(file);

                card.addEventListener('click', () => {
                    activePhotoIndex = idx;
                    renderPhotoMultiGallery();
                });

                photoMultiThumbnails.appendChild(card);
            });

            if (files.length < 4) {
                const addTile = document.createElement('div');
                addTile.className = 'gallery-thumb-add-tile';
                addTile.title = 'Add another face photo (up to 4)';
                addTile.innerHTML = `<i class="fa-solid fa-plus"></i><span>Angle</span>`;
                addTile.addEventListener('click', (e) => {
                    e.stopPropagation();
                    photoSourceFileInput.click();
                });
                photoMultiThumbnails.appendChild(addTile);
            }
        }
    }

    // Photo Source Input Listeners
    btnBrowsePhotoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        photoSourceFileInput.click();
    });

    if (btnAddMorePhotoSource) {
        btnAddMorePhotoSource.addEventListener('click', (e) => {
            e.stopPropagation();
            photoSourceFileInput.click();
        });
    }

    photoSourceDropzone.addEventListener('click', (e) => {
        if (!state.photo.sourceFile && state.photo.sourceFiles.length === 0 && !state.photo.sourceTemplate) {
            photoSourceFileInput.click();
        }
    });

    photoSourceFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            addPhotoSourceFiles(e.target.files);
            photoSourceFileInput.value = ''; // Reset to allow re-selection
        }
    });

    btnRemovePhotoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        clearPhotoSource();
    });

    // =========================================================================
    // PHOTO TARGET HANDLERS
    // =========================================================================
    function selectPhotoTargetPreset(tgt, el) {
        photoTargetPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.photo.targetFile = null;
        state.photo.targetTemplate = tgt.id;

        photoTargetPreviewImg.src = tgt.url;
        photoTargetEmptyState.classList.add('hidden');
        photoTargetPreviewState.classList.remove('hidden');
    }

    btnBrowsePhotoTarget.addEventListener('click', (e) => {
        e.stopPropagation();
        photoTargetFileInput.click();
    });

    photoTargetDropzone.addEventListener('click', () => {
        if (!state.photo.targetFile && !state.photo.targetTemplate) {
            photoTargetFileInput.click();
        }
    });

    photoTargetFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handlePhotoTargetFile(e.target.files[0]);
        }
    });

    function handlePhotoTargetFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file (JPG, PNG, WEBP).');
            return;
        }
        state.photo.targetFile = file;
        state.photo.targetTemplate = null;
        photoTargetPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        const reader = new FileReader();
        reader.onload = (e) => {
            photoTargetPreviewImg.src = e.target.result;
            photoTargetEmptyState.classList.add('hidden');
            photoTargetPreviewState.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    btnRemovePhotoTarget.addEventListener('click', (e) => {
        e.stopPropagation();
        state.photo.targetFile = null;
        state.photo.targetTemplate = null;
        photoTargetFileInput.value = '';
        photoTargetPreviewImg.src = '';
        photoTargetPreviewState.classList.add('hidden');
        photoTargetEmptyState.classList.remove('hidden');
        photoTargetPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    });

    // Drag & Drop for Photo Dropzones
    setupDragDrop(photoSourceDropzone, (files) => addPhotoSourceFiles(files));
    setupDragDrop(photoTargetDropzone, (files) => handlePhotoTargetFile(files[0]));

    // =========================================================================
    // MULTI-PHOTO SOURCE LOGIC (VIDEO MODE)
    // =========================================================================
    let activeVideoSourceIndex = 0;

    function selectVideoSourcePreset(face, el) {
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.video.sourceFile = null;
        state.video.sourceFiles = [];
        state.video.sourceTemplate = face.id;

        videoSourcePreviewImg.src = face.url;
        videoSourceEmptyState.classList.add('hidden');
        videoSourcePreviewState.classList.remove('hidden');
        if (videoMultiGallery) videoMultiGallery.classList.add('hidden');
        videoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-check-circle"></i> Preset Face Loaded`;
    }

    function addVideoSourceFiles(newFilesList) {
        const valid = Array.from(newFilesList).filter(f => f.type.startsWith('image/'));
        if (!valid.length) {
            alert('Please select valid image file(s) (JPG, PNG, WEBP).');
            return;
        }

        for (let f of valid) {
            if (state.video.sourceFiles.length < 4) {
                state.video.sourceFiles.push(f);
            }
        }

        state.video.sourceFile = state.video.sourceFiles[0] || null;
        state.video.sourceTemplate = null;
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        activeVideoSourceIndex = state.video.sourceFiles.length - 1;
        renderVideoMultiGallery();
    }

    function removeVideoSourceFile(index) {
        state.video.sourceFiles.splice(index, 1);
        if (state.video.sourceFiles.length === 0) {
            clearVideoSource();
        } else {
            if (activeVideoSourceIndex >= state.video.sourceFiles.length) {
                activeVideoSourceIndex = state.video.sourceFiles.length - 1;
            }
            state.video.sourceFile = state.video.sourceFiles[0];
            renderVideoMultiGallery();
        }
    }

    function clearVideoSource() {
        state.video.sourceFile = null;
        state.video.sourceFiles = [];
        state.video.sourceTemplate = null;
        activeVideoSourceIndex = 0;
        videoSourceFileInput.value = '';
        videoSourcePreviewImg.src = '';
        videoSourcePreviewState.classList.add('hidden');
        if (videoMultiGallery) videoMultiGallery.classList.add('hidden');
        videoSourceEmptyState.classList.remove('hidden');
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    }

    function renderVideoMultiGallery() {
        const files = state.video.sourceFiles;
        if (files.length === 0) {
            clearVideoSource();
            return;
        }

        videoSourceEmptyState.classList.add('hidden');
        videoSourcePreviewState.classList.remove('hidden');
        if (videoMultiGallery) videoMultiGallery.classList.remove('hidden');

        const activeFile = files[activeVideoSourceIndex] || files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            videoSourcePreviewImg.src = e.target.result;
        };
        reader.readAsDataURL(activeFile);

        if (videoCountBadge) videoCountBadge.textContent = files.length;
        if (files.length > 1) {
            videoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-dna"></i> 3D Master Fusion (${files.length} Photos)`;
        } else {
            videoSourceFusionBadge.innerHTML = `<i class="fa-solid fa-check-circle"></i> Input Face Loaded`;
        }

        if (videoMultiThumbnails) {
            videoMultiThumbnails.innerHTML = '';
            const angleLabels = ["P1 Front", "P2 Left", "P3 Right", "P4 Smile"];

            files.forEach((file, idx) => {
                const card = document.createElement('div');
                card.className = `gallery-thumb-card ${idx === activeVideoSourceIndex ? 'active' : ''}`;
                card.title = `Photo ${idx + 1}: ${file.name} (Click to preview)`;

                const r = new FileReader();
                r.onload = (e) => {
                    card.innerHTML = `
                        <img src="${e.target.result}" alt="Photo ${idx + 1}">
                        <span class="gallery-thumb-badge">${angleLabels[idx] || `P${idx + 1}`}</span>
                        <button type="button" class="gallery-thumb-delete" title="Delete Photo ${idx + 1}"><i class="fa-solid fa-xmark"></i></button>
                    `;
                    card.querySelector('.gallery-thumb-delete').addEventListener('click', (ev) => {
                        ev.stopPropagation();
                        removeVideoSourceFile(idx);
                    });
                };
                r.readAsDataURL(file);

                card.addEventListener('click', () => {
                    activeVideoSourceIndex = idx;
                    renderVideoMultiGallery();
                });

                videoMultiThumbnails.appendChild(card);
            });

            if (files.length < 4) {
                const addTile = document.createElement('div');
                addTile.className = 'gallery-thumb-add-tile';
                addTile.title = 'Add another face photo (up to 4)';
                addTile.innerHTML = `<i class="fa-solid fa-plus"></i><span>Angle</span>`;
                addTile.addEventListener('click', (e) => {
                    e.stopPropagation();
                    videoSourceFileInput.click();
                });
                videoMultiThumbnails.appendChild(addTile);
            }
        }
    }

    // Video Source Input Listeners
    btnBrowseVideoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        videoSourceFileInput.click();
    });

    if (btnAddMoreVideoSource) {
        btnAddMoreVideoSource.addEventListener('click', (e) => {
            e.stopPropagation();
            videoSourceFileInput.click();
        });
    }

    videoSourceDropzone.addEventListener('click', () => {
        if (!state.video.sourceFile && state.video.sourceFiles.length === 0 && !state.video.sourceTemplate) {
            videoSourceFileInput.click();
        }
    });

    videoSourceFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            addVideoSourceFiles(e.target.files);
            videoSourceFileInput.value = '';
        }
    });

    btnRemoveVideoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        clearVideoSource();
    });

    // =========================================================================
    // VIDEO TARGET HANDLERS
    // =========================================================================
    function selectVideoPreset(vid, el) {
        videoPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.video.targetFile = null;
        state.video.targetTemplate = vid.id;

        videoTargetPreviewVideo.src = vid.url;
        videoTargetEmptyState.classList.add('hidden');
        videoTargetPreviewState.classList.remove('hidden');

        videoTargetPreviewVideo.onloadedmetadata = () => {
            const dur = videoTargetPreviewVideo.duration.toFixed(1);
            videoDurationBadge.innerHTML = `<i class="fa-solid fa-clock"></i> ${dur}s`;
        };

        extractPeopleFromVideo();
    }

    btnBrowseVideoTarget.addEventListener('click', (e) => {
        e.stopPropagation();
        videoTargetFileInput.click();
    });

    videoTargetDropzone.addEventListener('click', () => {
        if (!state.video.targetFile && !state.video.targetTemplate) {
            videoTargetFileInput.click();
        }
    });

    videoTargetFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleVideoTargetFile(e.target.files[0]);
        }
    });

    function handleVideoTargetFile(file) {
        if (!file.type.startsWith('video/')) {
            alert('Please select a valid video file (MP4, WEBM, MOV).');
            return;
        }
        state.video.targetFile = file;
        state.video.targetTemplate = null;
        state.video.selectedPersonId = null;
        state.video.selectedPersonEmbedding = null;
        videoPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        const videoUrl = URL.createObjectURL(file);
        videoTargetPreviewVideo.src = videoUrl;
        videoTargetEmptyState.classList.add('hidden');
        videoTargetPreviewState.classList.remove('hidden');

        videoTargetPreviewVideo.onloadedmetadata = () => {
            const dur = videoTargetPreviewVideo.duration.toFixed(1);
            videoDurationBadge.innerHTML = `<i class="fa-solid fa-clock"></i> ${dur}s`;
        };

        extractPeopleFromVideo();
    }

    btnRemoveVideoTarget.addEventListener('click', (e) => {
        e.stopPropagation();
        state.video.targetFile = null;
        state.video.targetTemplate = null;
        state.video.selectedPersonId = null;
        state.video.selectedPersonEmbedding = null;
        videoTargetFileInput.value = '';
        videoTargetPreviewVideo.src = '';
        videoTargetPreviewState.classList.add('hidden');
        videoTargetEmptyState.classList.remove('hidden');
        targetPeopleSection.classList.add('hidden');
        videoPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    });

    // Drag & Drop for Video Dropzones
    setupDragDrop(videoSourceDropzone, (files) => addVideoSourceFiles(files));
    setupDragDrop(videoTargetDropzone, (files) => handleVideoTargetFile(files[0]));

    // Multi-Person Video Extraction
    async function extractPeopleFromVideo() {
        if (!state.video.targetFile && !state.video.targetTemplate) return;

        targetPeopleSection.classList.remove('hidden');
        peopleDetectedCount.textContent = "Scanning faces...";
        peopleChipsContainer.innerHTML = '<span style="font-size:12px;color:#94a3b8;"><i class="fa-solid fa-spinner fa-spin"></i> Detecting unique faces in video...</span>';

        const formData = new FormData();
        if (state.video.targetFile) {
            formData.append('target_video', state.video.targetFile);
        } else if (state.video.targetTemplate) {
            formData.append('target_template', state.video.targetTemplate);
        }

        try {
            const res = await fetch('/api/extract-video-faces', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) throw new Error("Failed to scan faces");
            const data = await res.json();

            state.video.detectedPeople = data.faces || [];
            renderPeopleChips();
        } catch (e) {
            console.warn("Face detection error:", e);
            peopleDetectedCount.textContent = "Auto Mode";
            peopleChipsContainer.innerHTML = '<span style="font-size:12px;color:#94a3b8;">Primary face will be replaced automatically.</span>';
        }
    }

    function renderPeopleChips() {
        peopleChipsContainer.innerHTML = '';
        peopleDetectedCount.textContent = `${state.video.detectedPeople.length} Person(s) Found`;

        // 1. All/Primary chip
        const allChip = document.createElement('div');
        allChip.className = 'person-chip active';
        allChip.innerHTML = `
            <div class="person-chip-icon"><i class="fa-solid fa-users"></i></div>
            <span class="person-chip-name">All / Primary Face</span>
        `;
        allChip.addEventListener('click', () => {
            peopleChipsContainer.querySelectorAll('.person-chip').forEach(c => c.classList.remove('active'));
            allChip.classList.add('active');
            state.video.selectedPersonId = null;
            state.video.selectedPersonEmbedding = null;
        });
        peopleChipsContainer.appendChild(allChip);

        // 2. Individual person chips
        state.video.detectedPeople.forEach((person) => {
            const chip = document.createElement('div');
            chip.className = 'person-chip';
            chip.innerHTML = `
                <img src="${person.preview_url}" class="person-chip-avatar" alt="${person.label}">
                <span class="person-chip-name">${person.label}</span>
            `;
            chip.addEventListener('click', () => {
                peopleChipsContainer.querySelectorAll('.person-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                state.video.selectedPersonId = person.person_id;
                state.video.selectedPersonEmbedding = person.embedding;
            });
            peopleChipsContainer.appendChild(chip);
        });
    }

    function setupDragDrop(element, onFileDrop) {
        ['dragenter', 'dragover'].forEach(eventName => {
            element.addEventListener(eventName, (e) => {
                e.preventDefault();
                element.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            element.addEventListener(eventName, (e) => {
                e.preventDefault();
                element.classList.remove('dragover');
            });
        });

        element.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) onFileDrop(files);
        });
    }

    // =========================================================================
    // EXECUTE PHOTO FACE SWAP
    // =========================================================================
    btnStartPhotoSwap.addEventListener('click', async () => {
        const hasSource = (state.photo.sourceFiles && state.photo.sourceFiles.length > 0) || state.photo.sourceFile || state.photo.sourceTemplate;
        if (!hasSource) {
            alert('Please upload an Input Face Photo on the left side first!');
            return;
        }

        if (!state.photo.targetFile && !state.photo.targetTemplate) {
            alert('Please upload a Target Photo on the right side in which you want to swap the face!');
            return;
        }

        const formData = new FormData();
        if (state.photo.sourceFiles && state.photo.sourceFiles.length > 0) {
            state.photo.sourceFiles.forEach(f => {
                formData.append('source_files', f);
            });
        } else if (state.photo.sourceFile) {
            formData.append('source_file', state.photo.sourceFile);
        } else if (state.photo.sourceTemplate) {
            formData.append('source_template', state.photo.sourceTemplate);
        }

        if (state.photo.targetFile) {
            formData.append('target_file', state.photo.targetFile);
        } else if (state.photo.targetTemplate) {
            formData.append('target_template', state.photo.targetTemplate);
        }

        const useEnhancer = togglePhotoEnhancer?.checked ?? true;
        const useGrain = togglePhotoGrain?.checked ?? true;
        formData.append('use_enhancer', useEnhancer);
        formData.append('use_grain', useGrain);

        const countText = state.photo.sourceFiles.length > 1 ? ` (${state.photo.sourceFiles.length} Photos 3D Fusion)` : "";
        showProgressModal(`Processing Photo Face Swap${countText}...`, "Analyzing landmarks, directional lighting & neural 512x512 restoration...");

        try {
            const res = await fetch('/api/swap-photo', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start photo swap');
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            startPolling(data.job_id, 'photo');

        } catch (err) {
            hideProgressModal();
            alert(`Error: ${err.message}`);
        }
    });

    // =========================================================================
    // EXECUTE VIDEO FACE SWAP
    // =========================================================================
    btnStartVideoSwap.addEventListener('click', async () => {
        const hasSource = (state.video.sourceFiles && state.video.sourceFiles.length > 0) || state.video.sourceFile || state.video.sourceTemplate;
        if (!hasSource) {
            alert('Please upload an Input Face Photo on the left side first!');
            return;
        }

        if (!state.video.targetFile && !state.video.targetTemplate) {
            alert('Please upload a Target Video Clip on the right side!');
            return;
        }

        const formData = new FormData();
        if (state.video.sourceFiles && state.video.sourceFiles.length > 0) {
            state.video.sourceFiles.forEach(f => {
                formData.append('source_files', f);
            });
        } else if (state.video.sourceFile) {
            formData.append('source_file', state.video.sourceFile);
        } else if (state.video.sourceTemplate) {
            formData.append('source_template', state.video.sourceTemplate);
        }

        if (state.video.targetFile) {
            formData.append('target_video', state.video.targetFile);
        } else if (state.video.targetTemplate) {
            formData.append('target_template', state.video.targetTemplate);
        }

        const maxDuration = parseFloat(durationSelect.value) || 30.0;
        formData.append('max_duration', maxDuration);

        const useEnhancer = toggleVideoEnhancer?.checked ?? true;
        const useSmoothing = toggleVideoSmoothing?.checked ?? true;
        const useGrain = toggleVideoGrain?.checked ?? true;

        formData.append('use_enhancer', useEnhancer);
        formData.append('use_smoothing', useSmoothing);
        formData.append('use_grain', useGrain);

        if (state.video.selectedPersonId !== null) {
            formData.append('target_person_id', state.video.selectedPersonId);
            if (state.video.selectedPersonEmbedding) {
                formData.append('target_person_embedding', JSON.stringify(state.video.selectedPersonEmbedding));
            }
        }

        const countText = state.video.sourceFiles.length > 1 ? ` (${state.video.sourceFiles.length} Photos 3D Fusion)` : "";
        showProgressModal(`Processing Video Face Swap${countText}...`, "Rendering video frames with optical tracking, directional lighting & audio preservation...");

        try {
            const res = await fetch('/api/swap-video', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start video face swap');
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            startPolling(data.job_id, 'video');

        } catch (err) {
            hideProgressModal();
            alert(`Error: ${err.message}`);
        }
    });

    // =========================================================================
    // PROGRESS MODAL & FLOATING BACKGROUND WIDGET LOGIC
    // =========================================================================
    let isModalMinimized = false;

    function showProgressModal(title, msg) {
        isModalMinimized = false;
        modalTitle.textContent = title;
        modalStatusText.textContent = msg;
        progressBarFill.style.width = "0%";
        progressPercent.textContent = "0%";
        progressFrames.textContent = "Starting AI Engine...";
        progressEta.innerHTML = `<i class="fa-solid fa-hourglass-half"></i> ETA: Calculating...`;

        // Sync initial state of floating widget
        if (floatingTitle) floatingTitle.textContent = title;
        if (floatingPercent) floatingPercent.textContent = "0%";
        if (floatingBarFill) floatingBarFill.style.width = "0%";
        if (floatingFrames) floatingFrames.textContent = "Starting AI Engine...";
        if (floatingEta) floatingEta.innerHTML = `<i class="fa-solid fa-hourglass-half"></i> ETA: --`;

        progressModal.classList.remove('hidden');
        if (floatingProgressWidget) floatingProgressWidget.classList.add('hidden');
    }

    function minimizeProgressModal() {
        isModalMinimized = true;
        progressModal.classList.add('hidden');
        if (floatingProgressWidget) {
            floatingProgressWidget.classList.remove('hidden');
        }
    }

    function expandProgressModal() {
        isModalMinimized = false;
        if (floatingProgressWidget) {
            floatingProgressWidget.classList.add('hidden');
        }
        progressModal.classList.remove('hidden');
    }

    function cancelAndCloseJob() {
        if (confirm("Are you sure you want to stop/close this face swap process?")) {
            hideProgressModal();
            state.currentJobId = null;
        }
    }

    function hideProgressModal() {
        progressModal.classList.add('hidden');
        if (floatingProgressWidget) floatingProgressWidget.classList.add('hidden');
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }
    }

    // Modal Control Button Listeners
    if (btnModalMinimize) btnModalMinimize.addEventListener('click', minimizeProgressModal);
    if (btnInlineMinimize) btnInlineMinimize.addEventListener('click', minimizeProgressModal);
    if (btnModalClose) btnModalClose.addEventListener('click', cancelAndCloseJob);

    // Floating Widget Control Listeners
    if (btnFloatingExpand) btnFloatingExpand.addEventListener('click', expandProgressModal);
    if (floatingBodyClickable) floatingBodyClickable.addEventListener('click', expandProgressModal);
    if (btnFloatingCancel) btnFloatingCancel.addEventListener('click', cancelAndCloseJob);

    function startPolling(jobId, jobType) {
        state.pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/job/${jobId}`);
                if (!res.ok) return;

                const job = await res.json();
                const pct = job.progress || 0;
                const msg = job.message || "Processing...";

                // 1. Update Full Modal elements
                modalStatusText.textContent = msg;
                progressBarFill.style.width = `${pct}%`;
                progressPercent.textContent = `${pct}%`;

                // 2. Update Floating Widget elements
                if (floatingPercent) floatingPercent.textContent = `${pct}%`;
                if (floatingBarFill) floatingBarFill.style.width = `${pct}%`;

                let framesText = "";
                if (jobType === 'video' && job.current_frame && job.total_frames) {
                    framesText = `Frame ${job.current_frame}/${job.total_frames}`;
                } else if (jobType === 'photo') {
                    framesText = pct >= 100 ? "Photo Completed" : "Neural Face Enhancement...";
                } else {
                    framesText = msg;
                }

                progressFrames.textContent = framesText;
                if (floatingFrames) floatingFrames.textContent = framesText;

                let etaHtml = "";
                if (job.eta) {
                    etaHtml = `<i class="fa-solid fa-hourglass-half"></i> ETA: ${job.eta}`;
                } else {
                    etaHtml = `<i class="fa-solid fa-bolt"></i> Processing`;
                }

                progressEta.innerHTML = etaHtml;
                if (floatingEta) floatingEta.innerHTML = etaHtml;

                if (job.status === 'completed') {
                    hideProgressModal();
                    displayResults(job, job.type || jobType);
                } else if (job.status === 'failed') {
                    hideProgressModal();
                    alert(`Face Swap Failed: ${job.error || 'Unknown error occurred'}`);
                }
            } catch (e) {
                console.error("Polling error:", e);
            }
        }, 1000);
    }

    // =========================================================================
    // SMART REGENERATION & AI TUNING LOGIC
    // =========================================================================
    const resultVersionBadge = document.getElementById('resultVersionBadge');
    const btnTogglePreviousVersion = document.getElementById('btnTogglePreviousVersion');
    const btnRegenerateNow = document.getElementById('btnRegenerateNow');
    const btnRegenerateText = document.getElementById('btnRegenerateText');
    const regenCards = document.querySelectorAll('.regen-card');

    const sliderFidelity = document.getElementById('sliderFidelity');
    const valFidelity = document.getElementById('valFidelity');
    const sliderColor = document.getElementById('sliderColor');
    const valColor = document.getElementById('valColor');
    const sliderSharpen = document.getElementById('sliderSharpen');
    const valSharpen = document.getElementById('valSharpen');

    let selectedRegenPreset = 'auto_improve';
    let versionHistory = []; // list of { id, url, iteration, presetTitle }
    let viewingVersionIdx = -1;

    // Preset selection
    const presetSliderValues = {
        'auto_improve': { fidelity: 92, color: 24, sharpen: 22 },
        'max_likeness': { fidelity: 96, color: 16, sharpen: 20 },
        'ultra_hd': { fidelity: 93, color: 26, sharpen: 32 },
        'ambient_blend': { fidelity: 82, color: 38, sharpen: 10 }
    };

    regenCards.forEach(card => {
        card.addEventListener('click', () => {
            regenCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedRegenPreset = card.dataset.preset;

            const values = presetSliderValues[selectedRegenPreset];
            if (values) {
                sliderFidelity.value = values.fidelity;
                valFidelity.textContent = `${values.fidelity}%`;

                sliderColor.value = values.color;
                valColor.textContent = `${values.color}%`;

                sliderSharpen.value = values.sharpen;
                valSharpen.textContent = `${values.sharpen}%`;
            }

            const title = card.querySelector('h4').textContent;
            btnRegenerateText.textContent = `Regenerate with ${title}`;
        });
    });

    // Sliders event listeners
    sliderFidelity.addEventListener('input', (e) => {
        valFidelity.textContent = `${e.target.value}%`;
    });

    sliderColor.addEventListener('input', (e) => {
        valColor.textContent = `${e.target.value}%`;
    });

    sliderSharpen.addEventListener('input', (e) => {
        valSharpen.textContent = `${e.target.value}%`;
    });

    // Handle Regenerate Click
    btnRegenerateNow.addEventListener('click', async () => {
        const activeJobId = state.currentJobId || (versionHistory.length > 0 ? versionHistory[versionHistory.length - 1].id : null);
        if (!activeJobId) {
            alert('No previous face swap found to regenerate. Please perform an initial swap first.');
            return;
        }

        const payload = {
            job_id: activeJobId,
            tuning_preset: selectedRegenPreset,
            fidelity: parseFloat(sliderFidelity.value) / 100.0,
            color_strength: parseFloat(sliderColor.value) / 100.0,
            sharpen_amount: parseFloat(sliderSharpen.value) / 100.0
        };

        const activeCard = document.querySelector('.regen-card.active');
        const presetName = activeCard ? activeCard.querySelector('h4').textContent : "Enhanced Tuning";

        showProgressModal(`Regenerating (${presetName})...`, "AI applying adaptive hyperparameters for maximum likeness & clarity...");

        try {
            const res = await fetch('/api/regenerate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                let errMsg = 'Failed to start regeneration';
                try {
                    const err = await res.json();
                    errMsg = err.detail || errMsg;
                } catch (e) {
                    try {
                        const txt = await res.text();
                        if (txt) errMsg = txt;
                    } catch (_) {}
                }
                throw new Error(errMsg);
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            startPolling(data.job_id, data.type);

        } catch (err) {
            hideProgressModal();
            alert(`Regeneration Notice: ${err.message}`);
        }
    });

    // Version Comparison Toggle (v1 vs v2)
    btnTogglePreviousVersion.addEventListener('click', () => {
        if (versionHistory.length < 2) return;

        if (viewingVersionIdx === -1 || viewingVersionIdx === versionHistory.length - 1) {
            // View previous version (v1)
            viewingVersionIdx = 0;
        } else {
            // View latest version
            viewingVersionIdx = versionHistory.length - 1;
        }

        const targetVer = versionHistory[viewingVersionIdx];
        const cacheBustedUrl = `${targetVer.url}?t=${Date.now()}`;
        if (currentMode === 'photo') {
            swappedPhotoResult.src = cacheBustedUrl;
        } else {
            swappedVideoPlayer.src = cacheBustedUrl;
            swappedVideoPlayer.load();
            swappedVideoPlayer.play().catch(() => {});
        }

        resultVersionBadge.innerHTML = `<i class="fa-solid fa-code-branch"></i> Version ${targetVer.iteration} (${targetVer.presetTitle || 'Enhanced'})`;
        btnTogglePreviousVersion.innerHTML = viewingVersionIdx === versionHistory.length - 1 ? 
            `<i class="fa-solid fa-code-compare"></i> View v1` : 
            `<i class="fa-solid fa-code-compare"></i> View Latest (v${versionHistory[versionHistory.length - 1].iteration})`;
    });

    // =========================================================================
    // DISPLAY RESULTS
    // =========================================================================
    function displayResults(job, jobType) {
        state.currentJobId = job.id;
        const iteration = job.iteration || 1;
        const presetTitle = job.preset_title || (iteration === 1 ? 'Initial Swap' : 'Enhanced');
        const cacheBustedUrl = `${job.output_url}?t=${Date.now()}`;
        
        versionHistory.push({
            id: job.id,
            url: job.output_url,
            iteration: iteration,
            presetTitle: presetTitle
        });
        viewingVersionIdx = versionHistory.length - 1;

        // Version badge
        if (iteration > 1) {
            resultVersionBadge.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Version ${iteration} (${presetTitle})`;
            resultVersionBadge.style.background = "linear-gradient(90deg, rgba(99,102,241,0.3), rgba(236,72,153,0.3))";
            resultVersionBadge.style.borderColor = "rgba(236,72,153,0.5)";
            resultVersionBadge.style.color = "#f472b6";
        } else {
            resultVersionBadge.innerHTML = `<i class="fa-solid fa-code-branch"></i> Version 1 (Initial)`;
            resultVersionBadge.style.background = "rgba(99, 102, 241, 0.2)";
            resultVersionBadge.style.borderColor = "rgba(99, 102, 241, 0.35)";
            resultVersionBadge.style.color = "#a5b4fc";
        }

        // Toggle Compare Button
        if (versionHistory.length > 1) {
            btnTogglePreviousVersion.style.display = "inline-flex";
            btnTogglePreviousVersion.innerHTML = `<i class="fa-solid fa-code-compare"></i> View v1`;
        } else {
            btnTogglePreviousVersion.style.display = "none";
        }

        if (jobType === 'photo') {
            resultsTitle.textContent = iteration > 1 ? `Your Transformed Photo (Version ${iteration})` : "Your Transformed Photo";
            resultsSubtitle.textContent = "Preview side-by-side or download your HD face-swapped photo below.";
            downloadBtnText.textContent = `Download HD Photo (v${iteration})`;
            btnDownloadMedia.href = job.download_url || job.output_url;
            btnDownloadMedia.setAttribute('download', `swapped_photo_v${iteration}_${job.id}.jpg`);

            // Swapped Photo (with cache buster)
            swappedPhotoResult.src = cacheBustedUrl;
            swappedPhotoResult.classList.remove('hidden');
            swappedVideoPlayer.classList.add('hidden');

            // Original Target Photo
            if (state.photo.targetFile) {
                originalPhotoResult.src = URL.createObjectURL(state.photo.targetFile);
            } else if (photoTargetPreviewImg.src) {
                originalPhotoResult.src = photoTargetPreviewImg.src;
            }
            originalPhotoResult.classList.remove('hidden');
            originalVideoPlayer.classList.add('hidden');

        } else {
            // Video result
            resultsTitle.textContent = iteration > 1 ? `Your Transformed Video (Version ${iteration})` : "Your Transformed Video";
            resultsSubtitle.textContent = "Preview side-by-side or download your HD face-swapped video below.";
            downloadBtnText.textContent = `Download HD Video (v${iteration})`;
            btnDownloadMedia.href = job.download_url || job.output_url;
            btnDownloadMedia.setAttribute('download', `swapped_video_v${iteration}_${job.id}.mp4`);

            // Swapped Video (with cache buster)
            swappedVideoPlayer.src = cacheBustedUrl;
            swappedVideoPlayer.classList.remove('hidden');
            swappedPhotoResult.classList.add('hidden');
            swappedVideoPlayer.load();
            swappedVideoPlayer.play().catch(() => {});

            // Original Target Video
            if (state.video.targetFile) {
                originalVideoPlayer.src = URL.createObjectURL(state.video.targetFile);
            } else if (videoTargetPreviewVideo.src) {
                originalVideoPlayer.src = videoTargetPreviewVideo.src;
            }
            originalVideoPlayer.classList.remove('hidden');
            originalPhotoResult.classList.add('hidden');
        }

        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    btnNewSwap.addEventListener('click', () => {
        resultsSection.classList.add('hidden');
        versionHistory = [];
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // =========================================================================
    // LIVE CAMERA & VIDEO RECORDING MODULE
    // =========================================================================
    let activeLivePhotoIndex = 0;
    const offscreenCanvas = document.createElement('canvas');
    const offscreenCtx = offscreenCanvas.getContext('2d');
    let lastLiveSwapSendTime = 0;

    // Helper: Register Live Source Face on Backend
    async function registerLiveFaceOnServer(params) {
        try {
            const formData = new FormData();
            if (params.preset_name) {
                formData.append('preset_name', params.preset_name);
            } else if (params.files && params.files.length > 0) {
                params.files.forEach(f => formData.append('source_files', f));
            }

            const res = await fetch('/api/live/set-source', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to initialize live face');
            }

            const data = await res.json();
            return data.source_id;
        } catch (e) {
            console.error('Error registering live face:', e);
            return null;
        }
    }

    // Select Live Source Preset
    async function selectLiveSourcePreset(face, el) {
        if (liveSourcePresetsRow) {
            liveSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        }
        if (el) el.classList.add('active');

        state.live.sourceFile = null;
        state.live.sourceFiles = [];
        state.live.sourceTemplate = face.id;

        liveSourcePreviewImg.src = face.url;
        liveSourceEmptyState.classList.add('hidden');
        liveSourcePreviewState.classList.remove('hidden');
        if (liveMultiGallery) liveMultiGallery.classList.add('hidden');
        liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Initializing 3D Face...`;

        const sourceId = await registerLiveFaceOnServer({ preset_name: face.id });
        if (sourceId) {
            state.live.sourceId = sourceId;
            liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-bolt"></i> Live 3D Mask Ready`;
            if (liveFaceStatusText) liveFaceStatusText.textContent = 'Face Mask Ready';
        } else {
            liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Initialization Failed`;
        }
    }

    // Add Live Source Files (Multi-Photo Fusion)
    async function addLiveSourceFiles(files) {
        if (!files || files.length === 0) return;
        const valid = Array.from(files).filter(f => f.type.startsWith('image/'));
        if (valid.length === 0) return;

        const remaining = 4 - state.live.sourceFiles.length;
        const toAdd = valid.slice(0, remaining);

        toAdd.forEach(f => {
            state.live.sourceFiles.push(f);
        });

        state.live.sourceFile = state.live.sourceFiles[0];
        state.live.sourceTemplate = null;

        renderLiveMultiThumbnails();

        liveSourcePreviewImg.src = URL.createObjectURL(state.live.sourceFiles[activeLivePhotoIndex || 0]);
        liveSourceEmptyState.classList.add('hidden');
        liveSourcePreviewState.classList.remove('hidden');

        if (state.live.sourceFiles.length > 1) {
            liveMultiGallery.classList.remove('hidden');
            liveCountBadge.textContent = state.live.sourceFiles.length;
            liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Fusing ${state.live.sourceFiles.length} Photos...`;
        } else {
            liveMultiGallery.classList.add('hidden');
            liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Initializing 3D Face...`;
        }

        const sourceId = await registerLiveFaceOnServer({ files: state.live.sourceFiles });
        if (sourceId) {
            state.live.sourceId = sourceId;
            liveSourceFusionBadge.innerHTML = state.live.sourceFiles.length > 1
                ? `<i class="fa-solid fa-dna"></i> 3D Fused (${state.live.sourceFiles.length} Angles)`
                : `<i class="fa-solid fa-bolt"></i> Live 3D Mask Ready`;
        } else {
            liveSourceFusionBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Fusion Failed`;
        }
    }

    function renderLiveMultiThumbnails() {
        if (!liveMultiThumbnails) return;
        liveMultiThumbnails.innerHTML = '';
        state.live.sourceFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'gallery-thumbnail-item' + (index === activeLivePhotoIndex ? ' active' : '');
            item.innerHTML = `
                <img src="${URL.createObjectURL(file)}" alt="Angle ${index + 1}">
                <button type="button" class="btn-thumb-delete" title="Remove angle"><i class="fa-solid fa-xmark"></i></button>
            `;

            item.addEventListener('click', (e) => {
                if (e.target.closest('.btn-thumb-delete')) return;
                activeLivePhotoIndex = index;
                liveSourcePreviewImg.src = URL.createObjectURL(file);
                renderLiveMultiThumbnails();
            });

            const delBtn = item.querySelector('.btn-thumb-delete');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                state.live.sourceFiles.splice(index, 1);
                if (activeLivePhotoIndex >= state.live.sourceFiles.length) {
                    activeLivePhotoIndex = Math.max(0, state.live.sourceFiles.length - 1);
                }
                if (state.live.sourceFiles.length === 0) {
                    resetLiveSource();
                } else {
                    addLiveSourceFiles([]);
                }
            });

            liveMultiThumbnails.appendChild(item);
        });

        if (btnAddMoreLiveSource) {
            if (state.live.sourceFiles.length >= 4) {
                btnAddMoreLiveSource.classList.add('hidden');
            } else {
                btnAddMoreLiveSource.classList.remove('hidden');
            }
        }
    }

    function resetLiveSource() {
        state.live.sourceFile = null;
        state.live.sourceFiles = [];
        state.live.sourceTemplate = null;
        state.live.sourceId = null;
        activeLivePhotoIndex = 0;

        liveSourcePreviewImg.src = '';
        liveSourcePreviewState.classList.add('hidden');
        liveSourceEmptyState.classList.remove('hidden');
        if (liveMultiGallery) liveMultiGallery.classList.add('hidden');
        if (liveSourceFileInput) liveSourceFileInput.value = '';
    }

    // Live Source Upload Listeners
    if (btnBrowseLiveSource) btnBrowseLiveSource.addEventListener('click', () => liveSourceFileInput.click());
    if (btnAddMoreLiveSource) btnAddMoreLiveSource.addEventListener('click', () => liveSourceFileInput.click());
    if (liveSourceFileInput) {
        liveSourceFileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                addLiveSourceFiles(e.target.files);
            }
        });
    }
    if (btnRemoveLiveSource) btnRemoveLiveSource.addEventListener('click', resetLiveSource);

    // Live Webcam Manager
    async function startLiveCamera() {
        try {
            const resVal = liveResolutionSelect ? liveResolutionSelect.value : '480p';
            let width = 640;
            let height = 480;
            if (resVal === '720p') { width = 1280; height = 720; }
            else if (resVal === '360p') { width = 480; height = 360; }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: width },
                    height: { ideal: height },
                    facingMode: 'user'
                },
                audio: true
            });

            state.live.stream = stream;
            state.live.isCameraOn = true;

            liveWebcamVideo.srcObject = stream;
            await liveWebcamVideo.play();

            liveCamPlaceholder.classList.add('hidden');
            btnToggleCameraText.textContent = 'Stop Camera';
            btnToggleCamera.classList.remove('btn-outline');
            btnToggleCamera.classList.add('btn-danger');

            btnStartRecording.disabled = false;
            btnTakeLiveSnapshot.disabled = false;

            liveStatusText.textContent = 'LIVE';
            liveStatusHud.classList.add('hud-live');

            // Open Live WebSocket
            connectLiveWebSocket();

            // Set canvas size
            liveSwapCanvas.width = liveWebcamVideo.videoWidth || width;
            liveSwapCanvas.height = liveWebcamVideo.videoHeight || height;
            offscreenCanvas.width = liveSwapCanvas.width;
            offscreenCanvas.height = liveSwapCanvas.height;

            // Start animation frame loop
            runLiveStreamLoop();

        } catch (err) {
            console.error('Failed to access camera/mic:', err);
            alert('Could not access camera/microphone. Please ensure permissions are granted in browser settings.');
        }
    }

    function stopLiveCamera() {
        if (state.live.isRecording) {
            stopLiveRecording();
        }

        if (state.live.stream) {
            state.live.stream.getTracks().forEach(track => track.stop());
            state.live.stream = null;
        }

        if (state.live.ws) {
            state.live.ws.close();
            state.live.ws = null;
        }

        if (state.live.activeAnimationId) {
            cancelAnimationFrame(state.live.activeAnimationId);
            state.live.activeAnimationId = null;
        }

        state.live.isCameraOn = false;
        liveCamPlaceholder.classList.remove('hidden');
        btnToggleCameraText.textContent = 'Start Camera';
        btnToggleCamera.classList.remove('btn-danger');
        btnToggleCamera.classList.add('btn-outline');

        btnStartRecording.disabled = true;
        btnTakeLiveSnapshot.disabled = true;

        liveStatusText.textContent = 'Camera Off';
        liveStatusHud.classList.remove('hud-live');
        liveFpsVal.textContent = '0';
        liveLatencyVal.textContent = '0';
    }

    function connectLiveWebSocket() {
        if (state.live.ws && state.live.ws.readyState === WebSocket.OPEN) return;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/live-swap`;
        
        state.live.ws = new WebSocket(wsUrl);

        state.live.ws.onopen = () => {
            console.log('[LiveSwap WS] Connected successfully');
        };

        state.live.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.frame) {
                    const img = new Image();
                    img.onload = () => {
                        const ctx = liveSwapCanvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, liveSwapCanvas.width, liveSwapCanvas.height);
                        state.live.isProcessingFrame = false;

                        // Latency & Face Detected Status
                        if (liveLatencyVal && data.latency_ms !== undefined) {
                            liveLatencyVal.textContent = data.latency_ms;
                        }
                        if (liveFaceStatusText) {
                            liveFaceStatusText.textContent = data.detected ? 'Face Locked' : 'No Face in View';
                        }
                        if (liveFaceStatusBadge) {
                            if (data.detected) {
                                liveFaceStatusBadge.style.color = '#86efac';
                            } else {
                                liveFaceStatusBadge.style.color = '#fca5a5';
                            }
                        }
                    };
                    img.src = data.frame;
                } else {
                    state.live.isProcessingFrame = false;
                }
            } catch (e) {
                state.live.isProcessingFrame = false;
            }
        };

        state.live.ws.onerror = (e) => {
            console.error('[LiveSwap WS] Error:', e);
            state.live.isProcessingFrame = false;
        };

        state.live.ws.onclose = () => {
            console.log('[LiveSwap WS] Closed');
            state.live.isProcessingFrame = false;
        };
    }

    function runLiveStreamLoop() {
        if (!state.live.isCameraOn) return;

        const ctx = liveSwapCanvas.getContext('2d');
        const now = performance.now();

        // FPS Calculation
        state.live.frameCount++;
        if (now - state.live.lastFpsTime >= 1000) {
            state.live.fps = Math.round((state.live.frameCount * 1000) / (now - state.live.lastFpsTime));
            if (liveFpsVal) liveFpsVal.textContent = state.live.fps;
            state.live.frameCount = 0;
            state.live.lastFpsTime = now;
        }

        // Frame Processing: Send frame to WebSocket if swapping is enabled and ready
        if (
            state.live.isSwapping &&
            state.live.sourceId &&
            state.live.ws &&
            state.live.ws.readyState === WebSocket.OPEN &&
            !state.live.isProcessingFrame &&
            liveWebcamVideo.readyState >= 2 &&
            now - lastLiveSwapSendTime >= 33 // ~30 FPS throttle
        ) {
            lastLiveSwapSendTime = now;
            state.live.isProcessingFrame = true;

            // Draw to offscreen canvas
            offscreenCtx.drawImage(liveWebcamVideo, 0, 0, offscreenCanvas.width, offscreenCanvas.height);
            const quality = toggleLiveFastMode && toggleLiveFastMode.checked ? 0.72 : 0.85;
            const dataUrl = offscreenCanvas.toDataURL('image/jpeg', quality);

            state.live.ws.send(JSON.stringify({
                frame: dataUrl,
                source_id: state.live.sourceId,
                fast_mode: toggleLiveFastMode ? toggleLiveFastMode.checked : true,
                use_enhancer: toggleLiveEnhancer ? toggleLiveEnhancer.checked : false,
                color_strength: 0.28
            }));

        } else if (!state.live.isSwapping || !state.live.sourceId) {
            // Draw direct un-swapped video onto canvas
            if (liveWebcamVideo.readyState >= 2) {
                ctx.drawImage(liveWebcamVideo, 0, 0, liveSwapCanvas.width, liveSwapCanvas.height);
            }
            if (liveFaceStatusText) {
                liveFaceStatusText.textContent = state.live.sourceId ? 'Swap Paused' : 'Pick a Face Source';
            }
        }

        state.live.activeAnimationId = requestAnimationFrame(runLiveStreamLoop);
    }

    // Toggle Camera Buttons
    if (btnToggleCamera) {
        btnToggleCamera.addEventListener('click', () => {
            if (state.live.isCameraOn) {
                stopLiveCamera();
            } else {
                startLiveCamera();
            }
        });
    }

    if (btnStartCamFromPlaceholder) {
        btnStartCamFromPlaceholder.addEventListener('click', startLiveCamera);
    }

    // Flip Camera / Mirror
    if (btnFlipCamera) {
        btnFlipCamera.addEventListener('click', () => {
            state.live.isMirrored = !state.live.isMirrored;
            if (state.live.isMirrored) {
                liveSwapCanvas.classList.remove('unmirrored');
                btnFlipCamera.classList.remove('active');
            } else {
                liveSwapCanvas.classList.add('unmirrored');
                btnFlipCamera.classList.add('active');
            }
        });
    }

    // Toggle Face Swap on Canvas
    if (btnToggleLiveSwapOnCanvas) {
        btnToggleLiveSwapOnCanvas.addEventListener('click', () => {
            state.live.isSwapping = !state.live.isSwapping;
            if (state.live.isSwapping) {
                btnToggleLiveSwapOnCanvas.classList.add('active');
            } else {
                btnToggleLiveSwapOnCanvas.classList.remove('active');
            }
        });
    }

    // Live Video Recording (Synced with Audio)
    function startLiveRecording() {
        if (!state.live.isCameraOn) return;

        state.live.recordedChunks = [];
        const canvasStream = liveSwapCanvas.captureStream(30);

        // Add audio track if present
        if (state.live.stream && state.live.stream.getAudioTracks().length > 0) {
            canvasStream.addTrack(state.live.stream.getAudioTracks()[0]);
        }

        let mimeType = 'video/webm;codecs=vp8,opus';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = 'video/webm';
        }

        try {
            state.live.mediaRecorder = new MediaRecorder(canvasStream, {
                mimeType: mimeType,
                videoBitsPerSecond: 2500000
            });
        } catch (e) {
            state.live.mediaRecorder = new MediaRecorder(canvasStream);
        }

        state.live.mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                state.live.recordedChunks.push(e.data);
            }
        };

        state.live.mediaRecorder.onstop = () => {
            const blob = new Blob(state.live.recordedChunks, { type: 'video/webm' });
            const videoUrl = URL.createObjectURL(blob);
            
            liveRecordedVideoPlayer.src = videoUrl;
            btnDownloadRecordedVideo.href = videoUrl;
            btnDownloadRecordedVideo.setAttribute('download', `live_face_swap_${Date.now()}.webm`);
            
            const totalSec = Math.floor(state.live.recordElapsedMs / 1000);
            const mm = String(Math.floor(totalSec / 60)).padStart(2, '0');
            const ss = String(totalSec % 60).padStart(2, '0');
            recordedDurationBadge.innerHTML = `<i class="fa-solid fa-clock"></i> ${mm}:${ss}`;

            liveRecordResultCard.classList.remove('hidden');
            liveRecordResultCard.scrollIntoView({ behavior: 'smooth' });
        };

        state.live.mediaRecorder.start(250);
        state.live.isRecording = true;
        state.live.isPaused = false;
        state.live.recordStartTime = Date.now();
        state.live.recordElapsedMs = 0;

        // Update UI
        btnStartRecording.classList.add('recording-active');
        btnRecordText.textContent = 'Stop Recording';
        btnPauseRecording.classList.remove('hidden');
        liveRecordingTimerPill.classList.remove('hidden');

        clearInterval(state.live.recordTimerInterval);
        state.live.recordTimerInterval = setInterval(() => {
            if (!state.live.isPaused) {
                state.live.recordElapsedMs = Date.now() - state.live.recordStartTime;
                const totalSec = Math.floor(state.live.recordElapsedMs / 1000);
                const mm = String(Math.floor(totalSec / 60)).padStart(2, '0');
                const ss = String(totalSec % 60).padStart(2, '0');
                liveRecordDurationText.textContent = `${mm}:${ss}`;
            }
        }, 500);
    }

    function pauseLiveRecording() {
        if (!state.live.isRecording || !state.live.mediaRecorder) return;

        if (state.live.isPaused) {
            state.live.mediaRecorder.resume();
            state.live.isPaused = false;
            state.live.recordStartTime = Date.now() - state.live.recordElapsedMs;
            btnPauseText.textContent = 'Pause';
            btnPauseRecording.classList.remove('btn-success');
            btnPauseRecording.classList.add('btn-warning');
        } else {
            state.live.mediaRecorder.pause();
            state.live.isPaused = true;
            btnPauseText.textContent = 'Resume';
            btnPauseRecording.classList.remove('btn-warning');
            btnPauseRecording.classList.add('btn-success');
        }
    }

    function stopLiveRecording() {
        if (!state.live.isRecording || !state.live.mediaRecorder) return;

        clearInterval(state.live.recordTimerInterval);
        state.live.mediaRecorder.stop();
        state.live.isRecording = false;
        state.live.isPaused = false;

        btnStartRecording.classList.remove('recording-active');
        btnRecordText.textContent = 'Start Recording Video';
        btnPauseRecording.classList.add('hidden');
        liveRecordingTimerPill.classList.add('hidden');
    }

    if (btnStartRecording) {
        btnStartRecording.addEventListener('click', () => {
            if (state.live.isRecording) {
                stopLiveRecording();
            } else {
                startLiveRecording();
            }
        });
    }

    if (btnPauseRecording) {
        btnPauseRecording.addEventListener('click', pauseLiveRecording);
    }

    // Instant Photo Snapshot
    function takeLiveSnapshot() {
        if (!state.live.isCameraOn) return;

        const dataUrl = liveSwapCanvas.toDataURL('image/jpeg', 0.95);
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = `live_face_snapshot_${Date.now()}.jpg`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        // Flash HUD badge feedback
        if (liveStatusText) {
            const original = liveStatusText.textContent;
            liveStatusText.textContent = '📸 Snapshot Saved!';
            setTimeout(() => { liveStatusText.textContent = original; }, 1500);
        }
    }

    if (btnTakeLiveSnapshot) btnTakeLiveSnapshot.addEventListener('click', takeLiveSnapshot);
    if (btnSnapshotQuick) btnSnapshotQuick.addEventListener('click', takeLiveSnapshot);
    if (btnCloseRecordedResult) btnCloseRecordedResult.addEventListener('click', () => liveRecordResultCard.classList.add('hidden'));

    // =========================================================================
    // AI VIDEO CALL STUDIO MODULE (WEBRTC PEER-TO-PEER)
    // =========================================================================
    const rtcConfig = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' }
        ]
    };

    let callOffscreenCanvas = document.createElement('canvas');
    let callOffscreenCtx = callOffscreenCanvas.getContext('2d');
    let callAnimationId = null;
    let isCallProcessingFrame = false;
    let lastCallSwapSendTime = 0;
    let callLiveSwapWs = null;

    function generateRoomCode() {
        const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        let code = '';
        for (let i = 0; i < 6; i++) {
            code += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return `ROOM-${code}`;
    }

    function createCallRoom() {
        const code = generateRoomCode();
        callRoomInput.value = code;
        if (callRoomCodeDisplay) callRoomCodeDisplay.textContent = code;
        btnCopyCallLink.classList.remove('hidden');
        joinCallRoom(code);
    }

    if (btnCreateCallRoom) btnCreateCallRoom.addEventListener('click', createCallRoom);
    if (btnJoinCallRoom) {
        btnJoinCallRoom.addEventListener('click', () => {
            const code = (callRoomInput.value || '').trim().toUpperCase();
            if (!code) {
                alert('Please enter a valid room code.');
                return;
            }
            joinCallRoom(code);
        });
    }

    if (btnCopyCallLink) {
        btnCopyCallLink.addEventListener('click', () => {
            const code = callRoomInput.value;
            const fullUrl = `${window.location.origin}${window.location.pathname}?room=${code}`;
            navigator.clipboard.writeText(fullUrl).then(() => {
                copyLinkText.textContent = 'Copied!';
                setTimeout(() => { copyLinkText.textContent = 'Copy Link'; }, 2000);
            });
        });
    }

    if (btnShareCallCodeQuick) {
        btnShareCallCodeQuick.addEventListener('click', () => {
            const code = callRoomInput.value;
            navigator.clipboard.writeText(code).then(() => {
                alert(`Room code ${code} copied to clipboard! Share it with your friend.`);
            });
        });
    }

    // Auto-join room from URL query if present (?room=ROOM-123)
    const urlParams = new URLSearchParams(window.location.search);
    const roomParam = urlParams.get('room');
    if (roomParam) {
        setMode('video-call');
        callRoomInput.value = roomParam;
        setTimeout(() => joinCallRoom(roomParam), 500);
    }

    async function joinCallRoom(roomId) {
        state.call.roomId = roomId;
        callStatusText.textContent = `Connecting to ${roomId}...`;
        callStatusIndicator.querySelector('.status-dot').className = 'status-dot call-active';

        try {
            // 1. Get Local Camera & Microphone
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: true
            });

            state.call.localStream = stream;
            callLocalWebcamVideo.srcObject = stream;
            await callLocalWebcamVideo.play();

            callLocalCanvas.width = callLocalWebcamVideo.videoWidth || 640;
            callLocalCanvas.height = callLocalWebcamVideo.videoHeight || 480;
            callOffscreenCanvas.width = callLocalCanvas.width;
            callOffscreenCanvas.height = callLocalCanvas.height;

            // Start Live Face Swap Loop on Local Canvas
            startCallLocalSwapLoop();

            // 2. Connect Signaling WebSocket
            connectCallSignalingWs(roomId);

        } catch (err) {
            console.error('Call join error:', err);
            alert('Failed to access camera/microphone for video call.');
            callStatusText.textContent = 'Camera/Mic access denied';
        }
    }

    function connectCallSignalingWs(roomId) {
        if (state.call.ws) {
            state.call.ws.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/video-call/${roomId}/${state.call.clientId}`;
        
        state.call.ws = new WebSocket(wsUrl);

        state.call.ws.onopen = () => {
            callStatusText.textContent = `In Room: ${roomId} • Waiting for peer`;
        };

        state.call.ws.onmessage = async (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'user-joined') {
                callStatusText.textContent = `Peer joined! Establishing P2P WebRTC...`;
                setupPeerConnection(true); // We are offerer
            } else if (msg.type === 'offer') {
                setupPeerConnection(false);
                await state.call.peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
                const answer = await state.call.peerConnection.createAnswer();
                await state.call.peerConnection.setLocalDescription(answer);
                state.call.ws.send(JSON.stringify({
                    type: 'answer',
                    target: msg.sender,
                    sdp: answer
                }));
            } else if (msg.type === 'answer') {
                if (state.call.peerConnection) {
                    await state.call.peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
                }
            } else if (msg.type === 'ice-candidate') {
                if (state.call.peerConnection && msg.candidate) {
                    try {
                        await state.call.peerConnection.addIceCandidate(new RTCIceCandidate(msg.candidate));
                    } catch (e) {
                        console.error('Error adding ICE candidate:', e);
                    }
                }
            } else if (msg.type === 'user-left') {
                remoteWaitingOverlay.classList.remove('hidden');
                remoteLivePill.classList.add('hidden');
                callStatusText.textContent = `Peer disconnected • In Room: ${roomId}`;
                if (callRemoteVideo.srcObject) {
                    callRemoteVideo.srcObject = null;
                }
            }
        };

        state.call.ws.onerror = (e) => {
            console.error('[WebRTC Call WS] Error:', e);
        };
    }

    async function setupPeerConnection(isInitiator) {
        if (state.call.peerConnection) {
            state.call.peerConnection.close();
        }

        const pc = new RTCPeerConnection(rtcConfig);
        state.call.peerConnection = pc;

        // Capture local canvas video stream + microphone audio
        const localCanvasStream = callLocalCanvas.captureStream(30);
        if (state.call.localStream && state.call.localStream.getAudioTracks().length > 0) {
            localCanvasStream.addTrack(state.call.localStream.getAudioTracks()[0]);
        }

        localCanvasStream.getTracks().forEach(track => {
            pc.addTrack(track, localCanvasStream);
        });

        pc.onicecandidate = (event) => {
            if (event.candidate && state.call.ws && state.call.ws.readyState === WebSocket.OPEN) {
                state.call.ws.send(JSON.stringify({
                    type: 'ice-candidate',
                    candidate: event.candidate
                }));
            }
        };

        pc.ontrack = (event) => {
            state.call.remoteStream = event.streams[0];
            callRemoteVideo.srcObject = event.streams[0];
            remoteWaitingOverlay.classList.add('hidden');
            remoteLivePill.classList.remove('hidden');
            callStatusText.textContent = `Connected • P2P WebRTC Video Call`;
        };

        if (isInitiator) {
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            state.call.ws.send(JSON.stringify({
                type: 'offer',
                sdp: offer
            }));
        }
    }

    function startCallLocalSwapLoop() {
        // Dedicated live swap WebSocket for Video Call local stream
        if (!callLiveSwapWs || callLiveSwapWs.readyState !== WebSocket.OPEN) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            callLiveSwapWs = new WebSocket(`${protocol}//${window.location.host}/ws/live-swap`);

            callLiveSwapWs.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.frame) {
                        const img = new Image();
                        img.onload = () => {
                            const ctx = callLocalCanvas.getContext('2d');
                            ctx.drawImage(img, 0, 0, callLocalCanvas.width, callLocalCanvas.height);
                            isCallProcessingFrame = false;
                        };
                        img.src = data.frame;
                    } else {
                        isCallProcessingFrame = false;
                    }
                } catch (e) {
                    isCallProcessingFrame = false;
                }
            };

            callLiveSwapWs.onerror = () => { isCallProcessingFrame = false; };
            callLiveSwapWs.onclose = () => { isCallProcessingFrame = false; };
        }

        let callFrameCount = 0;
        let lastFpsCheck = performance.now();

        function callLoop() {
            const ctx = callLocalCanvas.getContext('2d');
            const now = performance.now();

            callFrameCount++;
            if (now - lastFpsCheck >= 1000) {
                const fps = Math.round((callFrameCount * 1000) / (now - lastFpsCheck));
                if (callLocalFpsVal) callLocalFpsVal.textContent = fps;
                callFrameCount = 0;
                lastFpsCheck = now;
            }

            if (
                state.call.isSwapOn &&
                state.call.sourceId &&
                callLiveSwapWs &&
                callLiveSwapWs.readyState === WebSocket.OPEN &&
                !isCallProcessingFrame &&
                callLocalWebcamVideo.readyState >= 2 &&
                now - lastCallSwapSendTime >= 35 // ~28 FPS
            ) {
                lastCallSwapSendTime = now;
                isCallProcessingFrame = true;

                callOffscreenCtx.drawImage(callLocalWebcamVideo, 0, 0, callOffscreenCanvas.width, callOffscreenCanvas.height);
                const dataUrl = callOffscreenCanvas.toDataURL('image/jpeg', 0.72);

                callLiveSwapWs.send(JSON.stringify({
                    frame: dataUrl,
                    source_id: state.call.sourceId,
                    fast_mode: true,
                    use_enhancer: false,
                    color_strength: 0.25
                }));

            } else if (!state.call.isSwapOn || !state.call.sourceId) {
                if (callLocalWebcamVideo.readyState >= 2) {
                    ctx.drawImage(callLocalWebcamVideo, 0, 0, callLocalCanvas.width, callLocalCanvas.height);
                }
            }

            callAnimationId = requestAnimationFrame(callLoop);
        }

        callAnimationId = requestAnimationFrame(callLoop);
    }

    // Dynamic In-Call Face Preset Switcher
    async function selectCallFacePreset(face, el) {
        if (callFaceAvatarsRow) {
            callFaceAvatarsRow.querySelectorAll('.call-face-avatar-item').forEach(a => a.classList.remove('active'));
        }
        if (el) el.classList.add('active');

        state.call.activeAvatarPreset = face.id;
        localSwapTag.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Swapping...`;

        const sourceId = await registerLiveFaceOnServer({ preset_name: face.id });
        if (sourceId) {
            state.call.sourceId = sourceId;
            state.call.isSwapOn = true;
            localSwapTag.innerHTML = `AI Swapped`;
            btnToggleCallSwap.classList.add('active');
        }
    }

    if (btnUploadCustomCallFace && callCustomFaceInput) {
        btnUploadCustomCallFace.addEventListener('click', () => callCustomFaceInput.click());
        callCustomFaceInput.addEventListener('change', async (e) => {
            if (e.target.files && e.target.files.length > 0) {
                const file = e.target.files[0];
                localSwapTag.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Loading...`;
                const sourceId = await registerLiveFaceOnServer({ files: [file] });
                if (sourceId) {
                    state.call.sourceId = sourceId;
                    state.call.isSwapOn = true;
                    localSwapTag.innerHTML = `Custom Mask`;
                    btnToggleCallSwap.classList.add('active');
                }
            }
        });
    }

    // In-Call Controls
    if (btnToggleCallMic) {
        btnToggleCallMic.addEventListener('click', () => {
            state.call.isMicOn = !state.call.isMicOn;
            if (state.call.localStream) {
                state.call.localStream.getAudioTracks().forEach(t => { t.enabled = state.call.isMicOn; });
            }
            if (state.call.isMicOn) {
                btnToggleCallMic.classList.remove('inactive');
                btnToggleCallMic.innerHTML = `<i class="fa-solid fa-microphone"></i>`;
            } else {
                btnToggleCallMic.classList.add('inactive');
                btnToggleCallMic.innerHTML = `<i class="fa-solid fa-microphone-slash"></i>`;
            }
        });
    }

    if (btnToggleCallCam) {
        btnToggleCallCam.addEventListener('click', () => {
            state.call.isCamOn = !state.call.isCamOn;
            if (state.call.localStream) {
                state.call.localStream.getVideoTracks().forEach(t => { t.enabled = state.call.isCamOn; });
            }
            if (state.call.isCamOn) {
                btnToggleCallCam.classList.remove('inactive');
                btnToggleCallCam.innerHTML = `<i class="fa-solid fa-video"></i>`;
                localCamOffOverlay.style.display = 'none';
            } else {
                btnToggleCallCam.classList.add('inactive');
                btnToggleCallCam.innerHTML = `<i class="fa-solid fa-video-slash"></i>`;
                localCamOffOverlay.style.display = 'flex';
            }
        });
    }

    if (btnToggleCallSwap) {
        btnToggleCallSwap.addEventListener('click', () => {
            state.call.isSwapOn = !state.call.isSwapOn;
            if (state.call.isSwapOn) {
                btnToggleCallSwap.classList.add('active');
                localSwapTag.textContent = 'AI Swapped';
                localSwapTag.style.display = 'inline-block';
            } else {
                btnToggleCallSwap.classList.remove('active');
                localSwapTag.style.display = 'none';
            }
        });
    }

    if (btnToggleCallScreenShare) {
        btnToggleCallScreenShare.addEventListener('click', async () => {
            if (!state.call.isScreenSharing) {
                try {
                    const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
                    state.call.screenStream = screenStream;
                    state.call.isScreenSharing = true;
                    btnToggleCallScreenShare.classList.add('active');

                    const screenTrack = screenStream.getVideoTracks()[0];
                    if (state.call.peerConnection) {
                        const senders = state.call.peerConnection.getSenders();
                        const videoSender = senders.find(s => s.track && s.track.kind === 'video');
                        if (videoSender) {
                            videoSender.replaceTrack(screenTrack);
                        }
                    }

                    screenTrack.onended = () => {
                        state.call.isScreenSharing = false;
                        btnToggleCallScreenShare.classList.remove('active');
                        // Restore canvas video track
                        const canvasTrack = callLocalCanvas.captureStream(30).getVideoTracks()[0];
                        if (state.call.peerConnection) {
                            const senders = state.call.peerConnection.getSenders();
                            const videoSender = senders.find(s => s.track && s.track.kind === 'video');
                            if (videoSender) videoSender.replaceTrack(canvasTrack);
                        }
                    };
                } catch (e) {
                    console.error('Screen sharing cancelled:', e);
                }
            } else {
                if (state.call.screenStream) {
                    state.call.screenStream.getTracks().forEach(t => t.stop());
                }
                state.call.isScreenSharing = false;
                btnToggleCallScreenShare.classList.remove('active');
            }
        });
    }

    if (btnToggleCallRecording) {
        btnToggleCallRecording.addEventListener('click', () => {
            if (!state.call.isCallRecording) {
                // Start call recording
                state.call.callRecordedChunks = [];
                const streamToRecord = callLocalCanvas.captureStream(30);
                if (state.call.localStream && state.call.localStream.getAudioTracks().length > 0) {
                    streamToRecord.addTrack(state.call.localStream.getAudioTracks()[0]);
                }

                try {
                    state.call.callRecorder = new MediaRecorder(streamToRecord, { mimeType: 'video/webm' });
                } catch (e) {
                    state.call.callRecorder = new MediaRecorder(streamToRecord);
                }

                state.call.callRecorder.ondataavailable = (e) => {
                    if (e.data && e.data.size > 0) state.call.callRecordedChunks.push(e.data);
                };

                state.call.callRecorder.onstop = () => {
                    const blob = new Blob(state.call.callRecordedChunks, { type: 'video/webm' });
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = `video_call_record_${Date.now()}.webm`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                };

                state.call.callRecorder.start(500);
                state.call.isCallRecording = true;
                btnToggleCallRecording.classList.add('recording');
            } else {
                if (state.call.callRecorder) {
                    state.call.callRecorder.stop();
                }
                state.call.isCallRecording = false;
                btnToggleCallRecording.classList.remove('recording');
            }
        });
    }

    function endCall() {
        if (state.call.isCallRecording && state.call.callRecorder) {
            state.call.callRecorder.stop();
        }

        if (state.call.peerConnection) {
            state.call.peerConnection.close();
            state.call.peerConnection = null;
        }

        if (state.call.ws) {
            state.call.ws.close();
            state.call.ws = null;
        }

        if (callLiveSwapWs) {
            callLiveSwapWs.close();
            callLiveSwapWs = null;
        }

        if (callAnimationId) {
            cancelAnimationFrame(callAnimationId);
            callAnimationId = null;
        }

        if (state.call.localStream) {
            state.call.localStream.getTracks().forEach(t => t.stop());
            state.call.localStream = null;
        }

        if (state.call.screenStream) {
            state.call.screenStream.getTracks().forEach(t => t.stop());
            state.call.screenStream = null;
        }

        remoteWaitingOverlay.classList.remove('hidden');
        remoteLivePill.classList.add('hidden');
        callRemoteVideo.srcObject = null;
        callStatusText.textContent = 'Call Ended. Ready to start new call.';
        callStatusIndicator.querySelector('.status-dot').className = 'status-dot call-idle';
        btnCopyCallLink.classList.add('hidden');
        callRoomInput.value = '';
    }

    if (btnEndCall) btnEndCall.addEventListener('click', endCall);
});

