jQuery(function ($) {
  $(document).ready(function () {
    /***************************add mobile menu***************************/
    $(".btn_open").click(function () {
      $(".btn_open").toggleClass("active");
      $(".btn_close").toggleClass("active");
      $(".header_menu").toggleClass("active");
      $("body").toggleClass("lock-scroll");
    });
    $(".btn_close").click(function () {
      $(".btn_open").toggleClass("active");
      $(".btn_close").toggleClass("active");
      $(".header_menu").toggleClass("active");
      $("body").toggleClass("lock-scroll");
    });
	  
	  
	  
    $(document).mouseup(function (e) {
      if (
        !$("header.site-header").is(e.target) &&
        $("header.site-header").has(e.target).length === 0
      ) {
        $(".btn_open").removeClass("active");
        $(".btn_close").removeClass("active");
        $(".header_menu").removeClass("active");
        $("body").removeClass("lock-scroll");
      }
    });
    /*************************** carousel ***************************/
    if ($(window).innerWidth() < 768) {
      $(".home-seven-carousel").addClass("owl-carousel");
      $(".home-seven-carousel").owlCarousel({
        loop: true,
        nav: false,
        navText: false,
        dots: false,
        autoplay: true,
        responsiveClass: true,
        lazyLoad: true,
        autoplayTimeout: 5000,
        autoplaySpeed: 1000,
        margin: 15,
        center: true,
        items: 1,
      });
    }
    $(".about-third-carousel").owlCarousel({
      loop: true,
      autoplay: true,
      responsiveClass: true,
      lazyLoad: true,
      autoPlaySpeed: 1000,
      autoplayTimeout: 3000,
      margin: 4,
      autoWidth: true,
      center: false,
      dots: false,
      nav: true,
      navContainer: ".about-third-arrows",
      navText: [$(".about-third-arrow-prev"), $(".about-third-arrow-next")],
      responsive: {
        0: {
          center: true,
          items: 1,
        },
        768: {
          items: 3,
        },
      },
    });
    /************************************************************************/

    /*************************** select ***************************/
    $(".form_contact_wraper .select-wraper select").addClass(
      "js-example-basic-single"
    );
    $(".js-example-basic-single").each(function () {
      $(this).select2({
        minimumResultsForSearch: Infinity,
        dropdownParent: $(this).closest(
          ".form_contact_wraper .select-wraper p"
        ),
      });
    });
    /*************************** end select ***************************/

    /*************************** height header ***************************/
    if (jQuery(window).innerWidth() > 768) {
      function HH() {
        var heiHeader = jQuery(".fixing").height();
        jQuery("header").height(heiHeader);
      }
      HH();

      // cacl height and position
      function FiH() {
        if (window.innerWidth > 600) {
          var tpFH =
            jQuery(".fixing").height() + jQuery("#wpadminbar").height();
        } else {
          var chCL = jQuery(".fixing").hasClass("activated");
          if (chCL == false) {
            var tpFH =
              jQuery(".fixing").height() + jQuery("#wpadminbar").height();
          } else {
            var tpFH = jQuery(".fixing").height();
          }
        }
        var formHei = jQuery(window).innerHeight() - tpFH;
        jQuery("header nav").css({ "max-height": formHei });
      }
      FiH();

      if (jQuery(window).innerWidth() > 600) {
        if ($("body").hasClass("admin-bar")) {
          var topHP = 0 + jQuery("#wpadminbar").height();
        } else {
          var topHP = 0;
        }
      } else {
        var topHP = 0;
      }

      // sticky header
      jQuery(window).scroll(function () {
        if (jQuery(window).scrollTop() > 150) {
          jQuery(".fixing").addClass("activated").css({ top: topHP });
          FiH();
        } else {
          jQuery(".fixing").removeClass("activated").attr("style", "");
          FiH();
        }
      }); // end scroll function
    }
    /*************************** end height header ***************************/
    $('#file-csv').on('change', function() {
      let fileInfoDiv = $('#file-info');
      fileInfoDiv.empty(); 
      if (this.files && this.files.length > 0) {
        let file = this.files[0];
        $('.part-csv').addClass('has-file');
        let fileName = file.name;
        fileInfoDiv.html('<span>' + fileName + '</span>');
      } else {
        $('.part-csv').removeClass('has-file');
        fileInfoDiv.empty();
      }
    });

    // btn modal and hidden field for promotions
    $('.js-btn-modal-book').click(function () {
      setTimeout(() => {
          $('.js-filed-book-hid-name').val($(this).attr('data-name'))
      }, 0)
    });
    $(document).on('closed', '.remodal', function () {
      $('.js-filed-book-hid-name').val('');
    });
  });
});

document.addEventListener('wpcf7mailsent', function(event) {
    // Закриваємо модалку через 4 секунди
    setTimeout(function() {
        var $activeModal = $('.remodal-wrapper.remodal-is-opened .remodal');
        if ($activeModal.length) {
            var inst = $activeModal.remodal();
            if (inst) inst.close();
        }
    }, 4000);
}, false);

// Коли Remodal закривається, скидаємо всі форми всередині нього
$(document).on('closed', '.remodal', function () {
    $(this).find('form').each(function () {
        this.reset();
    });
});


