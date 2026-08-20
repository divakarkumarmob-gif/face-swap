document.addEventListener('DOMContentLoaded', () => {
    // Current Active Mode ('photo' | 'video')
    let currentMode = 'photo';

    // Application State
    const state = {
        // Photo Mode State
        photo: {
            sourceFile: null,
            sourceTemplate: null,
            targetFile: null,
            targetTemplate: null
        },
        // Video Mode State
        video: {
            sourceFile: null,
            sourceTemplate: null,
            targetFile: null,
            targetTemplate: null,
            selectedPersonId: null,
            selectedPersonEmbedding: null,
            detectedPeople: []
        },
        currentJobId: null,
        pollInterval: null
    };

    // DOM Elements - Mode Switcher
    const tabPhoto = document.getElementById('tabPhoto');
    const tabVideo = document.getElementById('tabVideo');
    const photoModeContainer = document.getElementById('photoModeContainer');
    const videoModeContainer = document.getElementById('videoModeContainer');

    // DOM Elements - Photo Mode (Left: Source Photo, Right: Target Photo)
    const photoSourceDropzone = document.getElementById('photoSourceDropzone');
    const photoSourceFileInput = document.getElementById('photoSourceFileInput');
    const photoSourceEmptyState = document.getElementById('photoSourceEmptyState');
    const photoSourcePreviewState = document.getElementById('photoSourcePreviewState');
    const photoSourcePreviewImg = document.getElementById('photoSourcePreviewImg');
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

    // DOM Elements - Video Mode (Left: Source Photo, Right: Target Video)
    const videoSourceDropzone = document.getElementById('videoSourceDropzone');
    const videoSourceFileInput = document.getElementById('videoSourceFileInput');
    const videoSourceEmptyState = document.getElementById('videoSourceEmptyState');
    const videoSourcePreviewState = document.getElementById('videoSourcePreviewState');
    const videoSourcePreviewImg = document.getElementById('videoSourcePreviewImg');
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

    // DOM Elements - Modal & Results
    const progressModal = document.getElementById('progressModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalStatusText = document.getElementById('modalStatusText');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressPercent = document.getElementById('progressPercent');
    const progressFrames = document.getElementById('progressFrames');
    const progressEta = document.getElementById('progressEta');

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
    const engineStatusText = document.getElementById('engineStatusText');

    // =========================================================================
    // Mode Switching Logic
    // =========================================================================
    function switchMode(mode) {
        currentMode = mode;
        resultsSection.classList.add('hidden');

        if (mode === 'photo') {
            tabPhoto.classList.add('active');
            tabVideo.classList.remove('active');
            photoModeContainer.classList.remove('hidden');
            videoModeContainer.classList.add('hidden');
        } else {
            tabVideo.classList.add('active');
            tabPhoto.classList.remove('active');
            videoModeContainer.classList.remove('hidden');
            photoModeContainer.classList.add('hidden');
        }
    }

    tabPhoto.addEventListener('click', () => switchMode('photo'));
    tabVideo.addEventListener('click', () => switchMode('video'));

    // =========================================================================
    // Backend Status Check
    // =========================================================================
    async function checkStatus() {
        try {
            const res = await fetch('/api/status');
            if (res.ok) {
                const data = await res.json();
                engineStatusText.textContent = data.initialized ? "AI Engine Ready" : "AI Models Ready";
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

            // Populate Photo Source Presets & Video Source Presets
            if (data.faces && data.faces.length > 0) {
                renderFacePresets(data.faces, photoSourcePresetsRow, (face, thumb) => {
                    selectPhotoSourcePreset(face, thumb);
                });
                renderFacePresets(data.faces, videoSourcePresetsRow, (face, thumb) => {
                    selectVideoSourcePreset(face, thumb);
                });
            }

            // Populate Photo Target Presets
            const targetPhotos = (data.target_photos && data.target_photos.length > 0) ? data.target_photos : data.faces;
            if (targetPhotos && targetPhotos.length > 0) {
                renderFacePresets(targetPhotos, photoTargetPresetsRow, (item, thumb) => {
                    selectPhotoTargetPreset(item, thumb);
                });
            }

            // Populate Video Presets
            if (data.videos && data.videos.length > 0) {
                videoPresetsRow.innerHTML = '';
                data.videos.forEach(vid => {
                    const thumb = document.createElement('div');
                    thumb.className = 'preset-thumb';
                    thumb.title = vid.title;
                    thumb.innerHTML = `<video src="${vid.url}" muted></video>`;
                    thumb.addEventListener('click', () => selectVideoPreset(vid, thumb));
                    videoPresetsRow.appendChild(thumb);
                });
            }
        } catch (e) {
            console.warn("Could not load templates:", e);
        }
    }

    function renderFacePresets(items, container, onClick) {
        container.innerHTML = '';
        items.forEach(item => {
            const thumb = document.createElement('div');
            thumb.className = 'preset-thumb';
            thumb.title = item.title;
            thumb.innerHTML = `<img src="${item.url}" alt="${item.title}">`;
            thumb.addEventListener('click', () => onClick(item, thumb));
            container.appendChild(thumb);
        });
    }

    loadTemplates();

    // =========================================================================
    // PHOTO MODE HANDLERS
    // =========================================================================
    function selectPhotoSourcePreset(face, el) {
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.photo.sourceFile = null;
        state.photo.sourceTemplate = face.id;

        photoSourcePreviewImg.src = face.url;
        photoSourceEmptyState.classList.add('hidden');
        photoSourcePreviewState.classList.remove('hidden');
    }

    function selectPhotoTargetPreset(photo, el) {
        photoTargetPresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.photo.targetFile = null;
        state.photo.targetTemplate = photo.id;

        photoTargetPreviewImg.src = photo.url;
        photoTargetEmptyState.classList.add('hidden');
        photoTargetPreviewState.classList.remove('hidden');
    }

    // Photo Source Upload
    btnBrowsePhotoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        photoSourceFileInput.click();
    });

    photoSourceDropzone.addEventListener('click', () => {
        if (!state.photo.sourceFile && !state.photo.sourceTemplate) {
            photoSourceFileInput.click();
        }
    });

    photoSourceFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handlePhotoSourceFile(e.target.files[0]);
        }
    });

    function handlePhotoSourceFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file (JPG, PNG, WEBP).');
            return;
        }
        state.photo.sourceFile = file;
        state.photo.sourceTemplate = null;
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        const reader = new FileReader();
        reader.onload = (e) => {
            photoSourcePreviewImg.src = e.target.result;
            photoSourceEmptyState.classList.add('hidden');
            photoSourcePreviewState.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    btnRemovePhotoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        state.photo.sourceFile = null;
        state.photo.sourceTemplate = null;
        photoSourceFileInput.value = '';
        photoSourcePreviewImg.src = '';
        photoSourcePreviewState.classList.add('hidden');
        photoSourceEmptyState.classList.remove('hidden');
        photoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    });

    // Photo Target Upload (Right Side)
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
    setupDragDrop(photoSourceDropzone, handlePhotoSourceFile);
    setupDragDrop(photoTargetDropzone, handlePhotoTargetFile);

    // =========================================================================
    // VIDEO MODE HANDLERS
    // =========================================================================
    function selectVideoSourcePreset(face, el) {
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
        el.classList.add('active');

        state.video.sourceFile = null;
        state.video.sourceTemplate = face.id;

        videoSourcePreviewImg.src = face.url;
        videoSourceEmptyState.classList.add('hidden');
        videoSourcePreviewState.classList.remove('hidden');
    }

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

    // Video Source Upload
    btnBrowseVideoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        videoSourceFileInput.click();
    });

    videoSourceDropzone.addEventListener('click', () => {
        if (!state.video.sourceFile && !state.video.sourceTemplate) {
            videoSourceFileInput.click();
        }
    });

    videoSourceFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleVideoSourceFile(e.target.files[0]);
        }
    });

    function handleVideoSourceFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select a valid image file (JPG, PNG, WEBP).');
            return;
        }
        state.video.sourceFile = file;
        state.video.sourceTemplate = null;
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));

        const reader = new FileReader();
        reader.onload = (e) => {
            videoSourcePreviewImg.src = e.target.result;
            videoSourceEmptyState.classList.add('hidden');
            videoSourcePreviewState.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
    }

    btnRemoveVideoSource.addEventListener('click', (e) => {
        e.stopPropagation();
        state.video.sourceFile = null;
        state.video.sourceTemplate = null;
        videoSourceFileInput.value = '';
        videoSourcePreviewImg.src = '';
        videoSourcePreviewState.classList.add('hidden');
        videoSourceEmptyState.classList.remove('hidden');
        videoSourcePresetsRow.querySelectorAll('.preset-thumb').forEach(t => t.classList.remove('active'));
    });

    // Video Target Upload
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
            const dur = videoTargetPreviewVideo.duration;
            videoDurationBadge.innerHTML = `<i class="fa-solid fa-clock"></i> ${dur.toFixed(1)}s`;
            if (dur > 30) {
                videoDurationBadge.innerHTML += ` <span style="color:#f59e0b">(Max 30s)</span>`;
            }
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
    setupDragDrop(videoSourceDropzone, handleVideoSourceFile);
    setupDragDrop(videoTargetDropzone, handleVideoTargetFile);

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
            if (files.length > 0) onFileDrop(files[0]);
        });
    }

    // =========================================================================
    // EXECUTE PHOTO FACE SWAP
    // =========================================================================
    btnStartPhotoSwap.addEventListener('click', async () => {
        if (!state.photo.sourceFile && !state.photo.sourceTemplate) {
            alert('Please upload an Input Face Photo on the left side first!');
            return;
        }

        if (!state.photo.targetFile && !state.photo.targetTemplate) {
            alert('Please upload a Target Photo on the right side in which you want to swap the face!');
            return;
        }

        const formData = new FormData();
        if (state.photo.sourceFile) {
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

        showProgressModal("Processing Photo Face Swap...", "Analyzing faces & blending high-definition neural swap...");

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
        if (!state.video.sourceFile && !state.video.sourceTemplate) {
            alert('Please upload an Input Face Photo on the left side first!');
            return;
        }

        if (!state.video.targetFile && !state.video.targetTemplate) {
            alert('Please upload a Target Video Clip on the right side!');
            return;
        }

        const formData = new FormData();
        if (state.video.sourceFile) {
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

        showProgressModal("Processing Video Face Swap...", "Rendering video frames with facial tracking & audio preserve...");

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
    // PROGRESS MODAL & POLLING
    // =========================================================================
    function showProgressModal(title, msg) {
        modalTitle.textContent = title;
        modalStatusText.textContent = msg;
        progressBarFill.style.width = "0%";
        progressPercent.textContent = "0%";
        progressFrames.textContent = "Starting AI Engine...";
        progressEta.innerHTML = `<i class="fa-solid fa-hourglass-half"></i> ETA: Calculating...`;
        progressModal.classList.remove('hidden');
    }

    function hideProgressModal() {
        progressModal.classList.add('hidden');
        if (state.pollInterval) {
            clearInterval(state.pollInterval);
            state.pollInterval = null;
        }
    }

    function startPolling(jobId, jobType) {
        state.pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/job/${jobId}`);
                if (!res.ok) return;

                const job = await res.json();
                modalStatusText.textContent = job.message || "Processing...";
                progressBarFill.style.width = `${job.progress || 0}%`;
                progressPercent.textContent = `${job.progress || 0}%`;

                if (jobType === 'video' && job.current_frame && job.total_frames) {
                    progressFrames.textContent = `Frame ${job.current_frame}/${job.total_frames}`;
                } else if (jobType === 'photo') {
                    progressFrames.textContent = job.progress >= 100 ? "Photo Completed" : "Processing Photo...";
                }

                if (job.eta) {
                    progressEta.innerHTML = `<i class="fa-solid fa-hourglass-half"></i> ETA: ${job.eta}`;
                } else {
                    progressEta.innerHTML = `<i class="fa-solid fa-bolt"></i> Processing`;
                }

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
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start regeneration');
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            startPolling(data.job_id, data.type);

        } catch (err) {
            hideProgressModal();
            alert(`Regeneration Error: ${err.message}`);
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
});
