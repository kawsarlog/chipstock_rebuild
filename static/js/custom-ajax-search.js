jQuery(document).ready(function ($) {
  const modalWrapper = $('.js-select-model');
  const wrapperItems = $('.js-modal-items');
  const btnSearch = $('.js-btn-search');
  let debounceTimer = null;

  const setFieldAndOpenSearch = (results = []) => {
    wrapperItems.html('');

    if (results.length) {
      modalWrapper.removeClass('hide');

      results.forEach((el) => {
        if (el?.part?.manufacturer) {
          const manufacturer = el.part.manufacturer;
          const partName = el.part.name;
          const searchQuery = `${manufacturer.name} ${partName}`;

          wrapperItems.append(`
            <a href="/search?q=${encodeURIComponent(searchQuery)}">
              <span>${manufacturer.name}</span> ${partName}
            </a>
          `);
        }
      });
    } else {
      modalWrapper.addClass('hide');
    }
  }

  btnSearch.on('click', function () {
    const query = $("#search-input").val();
    if (query.trim()) {
      window.location.href = `/search?q=${encodeURIComponent(query)}`;
    }
  });

  $("#search-input").on("input", function () {
    btnSearch.addClass('loading');

    if (debounceTimer) clearTimeout(debounceTimer);

    debounceTimer = setTimeout(() => {
      const query = $(this).val().trim();

      if (!query) {
        setFieldAndOpenSearch([]);
        btnSearch.removeClass('loading');
        return;
      }

      $.ajax({
        url: wp_ajax_object.ajax_url,
        method: "POST",
        data: {
          action: "search_external_data",
          query: query,
        },
        success: function (response) {
          const results = response?.data?.data?.supSearch?.results || [];
          setFieldAndOpenSearch(results);
          console.log("✅ Результат:", response);

          btnSearch.removeClass('loading');
        },
        error: function (error) {
          console.log("❌ Помилка:", error);
          btnSearch.removeClass('loading');
        },
      });
    }, 400);
  });
});
