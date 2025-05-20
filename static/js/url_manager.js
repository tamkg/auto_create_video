document.addEventListener("DOMContentLoaded", () => {
  const urlInput = document.getElementById("urlInput");
  const playlistOption = document.getElementById("playlistOption");
  const fetchPlaylistCheckbox = document.getElementById("fetchPlaylistCheckbox");
  const titleInput = document.getElementById("titleInput");
  const playlistVideosContainer = document.getElementById("playlistVideosContainer");
  const playlistVideosList = document.getElementById("playlistVideosList");
  const fetchTitleBtn = document.getElementById("fetchTitleBtn");
  const titleSpinner = document.getElementById("titleSpinner");
  const urlForm = document.getElementById("urlForm");

  // Hiển thị/ẩn checkbox lấy playlist dựa trên URL
  urlInput.addEventListener("input", () => {
    const val = urlInput.value.toLowerCase();
    if (val.includes("playlist")) {
      playlistOption.style.display = "block";
    } else {
      playlistOption.style.display = "none";
      fetchPlaylistCheckbox.checked = false;
      playlistVideosContainer.classList.add("visually-hidden");
      playlistVideosList.innerHTML = "";
    }
  });

  // Khi checkbox lấy playlist thay đổi
  fetchPlaylistCheckbox.addEventListener("change", async () => {
    titleInput.value = ""; // reset title

    if (!fetchPlaylistCheckbox.checked) {
      playlistVideosContainer.classList.add("visually-hidden");
      playlistVideosList.innerHTML = "";
      return;
    }

    const url = urlInput.value.trim();
    if (!url) {
      alert("Vui lòng nhập URL trước khi lấy playlist.");
      fetchPlaylistCheckbox.checked = false;
      return;
    }

    playlistVideosList.innerHTML = '<li><em>Đang tải danh sách video...</em></li>';
    playlistVideosContainer.classList.remove("visually-hidden");

    try {
      const res = await fetch("/url/fetch_playlist_videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (data.success && Array.isArray(data.videos) && data.videos.length > 0) {
        playlistVideosList.innerHTML = "";
        data.videos.forEach(video => {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = video.url || "#";
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          a.textContent = video.title || video.url || "(Không có tiêu đề)";
          li.appendChild(a);
          playlistVideosList.appendChild(li);
        });
      } else {
        playlistVideosList.innerHTML = "<li><em>Không tìm thấy video trong playlist hoặc lỗi server.</em></li>";
      }
    } catch (error) {
      playlistVideosList.innerHTML = `<li><em>Lỗi khi lấy danh sách video playlist. Hãy thử ấn nút Lấy tiêu đề để xem URL đầy đủ.</em></li>`;
    }
  });

  // Xử lý lấy tiêu đề video
  fetchTitleBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      alert("❌ Vui lòng nhập URL trước khi lấy tiêu đề.");
      return;
    }
    if (fetchPlaylistCheckbox.checked) {
      alert("❌ Đang chọn lấy toàn bộ playlist, không thể lấy tiêu đề đơn lẻ.");
      return;
    }

    fetchTitleBtn.disabled = true;
    titleSpinner.classList.remove("visually-hidden");

    try {
      const res = await fetch("/url/fetch_title", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (data.success) {
        if (data.data?.is_playlist) {
          titleInput.value = data.data.playlist_title || "";
          playlistVideosList.innerHTML = "";
          data.data.playlist_urls.forEach(videoUrl => {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = videoUrl;
            a.target = "_blank";
            a.rel = "noopener noreferrer";
            a.textContent = videoUrl;
            li.appendChild(a);
            playlistVideosList.appendChild(li);
          });
          playlistVideosContainer.classList.remove("visually-hidden");
          playlistOption.style.display = "block";
          fetchPlaylistCheckbox.checked = true;
        } else if (data.data?.title) {
          titleInput.value = data.data.title;
          playlistVideosContainer.classList.add("visually-hidden");
          playlistVideosList.innerHTML = "";
          playlistOption.style.display = "none";
          fetchPlaylistCheckbox.checked = false;
        } else {
          alert("❌ Không lấy được tiêu đề. Vui lòng kiểm tra lại URL.");
        }
      } else {
        alert("❌ " + (data.message || "Lỗi khi lấy tiêu đề."));
      }
    } catch {
      alert("❌ Có lỗi khi lấy tiêu đề.");
    } finally {
      fetchTitleBtn.disabled = false;
      titleSpinner.classList.add("visually-hidden");
    }
  });

  // Xử lý submit form thêm URL
  urlForm.addEventListener("submit", (e) => {
    // Đảm bảo checkbox đúng trạng thái trước khi gửi form
    if (playlistOption.style.display === "none") {
      fetchPlaylistCheckbox.checked = false;
    } else {
      // Giữ nguyên giá trị checkbox
    }
  });
});

// Modal sửa URL (Bootstrap 5 chuẩn)
const editUrlModal = new bootstrap.Modal(document.getElementById("editUrlModal"));

function editUrl(id, url, title, category) {
  document.getElementById("editUrlId").value = id;
  document.getElementById("editUrlInput").value = url;
  document.getElementById("editTitleInput").value = title;
  document.getElementById("editCategoryInput").value = category || "None";
  editUrlModal.show();
}

async function saveEditUrl() {
  const id = document.getElementById("editUrlId").value;
  const url = document.getElementById("editUrlInput").value.trim();
  const title = document.getElementById("editTitleInput").value.trim();
  const category = document.getElementById("editCategoryInput").value;

  if (!url) {
    alert("❌ URL không được để trống.");
    return;
  }

  try {
    const res = await fetch("/url/edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, url, title, category }),
    });
    const data = await res.json();

    if (data.success) {
      location.reload();
    } else {
      alert("❌ " + (data.message || "Lỗi khi lưu thay đổi."));
    }
  } catch {
    alert("❌ Có lỗi khi gửi yêu cầu.");
  }
}

async function deleteUrl(id) {
  if (!confirm("Bạn có chắc muốn xóa URL này?")) return;

  try {
    const res = await fetch("/url/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const data = await res.json();

    if (data.success) {
      location.reload();
    } else {
      alert("❌ " + (data.message || "Lỗi khi xóa URL."));
    }
  } catch {
    alert("❌ Có lỗi khi gửi yêu cầu.");
  }
}


document.getElementById('fetchTikTokBtn').addEventListener('click', async function() {
    const channelUrl = document.getElementById('tiktokChannelInput').value.trim();
    if (!channelUrl) {
        alert("Vui lòng nhập URL kênh TikTok.");
        return;
    }

    const tiktokSpinner = document.getElementById('tiktokSpinner');
    tiktokSpinner.classList.remove('visually-hidden');

    try {
        const response = await fetch('/url/fetch_tiktok_videos', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: channelUrl })
        });

        const result = await response.json();
        tiktokSpinner.classList.add('visually-hidden');

        if (result.success) {
            const videos = result.data.videos;
            const tiktokVideosList = document.getElementById('tiktokVideosList');
            const addAllTikTokBtn = document.getElementById('addAllTikTokBtn');

            tiktokVideosList.innerHTML = '';

            videos.forEach(videoUrl => {
                const li = document.createElement('li');
                li.textContent = videoUrl;
                tiktokVideosList.appendChild(li);
            });

            // Hiển thị danh sách và nút nếu có video
            if (videos.length > 0) {
                document.getElementById('tiktokVideosContainer').classList.remove('visually-hidden');
                addAllTikTokBtn.classList.remove('visually-hidden');
            } else {
                addAllTikTokBtn.classList.add('visually-hidden');
            }
        } else {
            alert(result.message);
        }
    } catch (error) {
        tiktokSpinner.classList.add('visually-hidden');
        alert("❌ Đã xảy ra lỗi khi lấy video từ kênh TikTok.");
    }
});


// Xử lý thêm tất cả video vào danh sách URL
document.getElementById('addAllTikTokBtn').addEventListener('click', async function() {
    const tiktokVideosList = document.getElementById('tiktokVideosList');
    const urls = Array.from(tiktokVideosList.querySelectorAll('li')).map(li => li.textContent);

    if (urls.length === 0) {
        alert("Không có video nào để thêm.");
        return;
    }

    const batchSize = 50; // Số lượng URL mỗi lần gửi
    let totalAdded = 0;
    let errors = [];

    for (let i = 0; i < urls.length; i += batchSize) {
        const batchUrls = urls.slice(i, i + batchSize);
        const response = await fetch('/url/add_batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ urls: batchUrls, category: "TikTok" })
        });

        const result = await response.json();
        if (result.success) {
            totalAdded += result.data.added;
        } else {
            errors.push(result.message);
        }

        // Hiển thị tiến trình
        document.getElementById('addAllTikTokBtn').textContent = `Đang thêm... ${i + batchUrls.length}/${urls.length}`;
    }

    // Thông báo kết quả
    if (errors.length > 0) {
        alert(`✅ Đã thêm ${totalAdded} video từ TikTok vào database.\n❌ Một số lỗi xảy ra:\n${errors.join("\n")}`);
    } else {
        alert(`✅ Đã thêm ${totalAdded} video từ TikTok vào database.`);
    }

    window.location.reload();
});