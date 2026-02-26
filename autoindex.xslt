<?xml version="1.0" encoding="UTF-8" ?>
<!--
  autoindex.xslt - XSLT stylesheet for nginx autoindex XML output.

  Transforms nginx's autoindex XML into styled HTML matching the
  generate-index.py output.  Deployed as /.autoindex.xslt on the
  download server.

  nginx config:
    autoindex on;
    autoindex_format xml;
    xslt_stylesheet /home/mirror/downloads/.autoindex.xslt;
    xslt_string_param path $uri;
-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output
        method="html"
        encoding="UTF-8"
        indent="no"
        doctype-system="about:legacy-compat"
    />
<xsl:param name="path" select="'/'" />

<xsl:template match="/">
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="/.style.css" />
<title>Index of <xsl:value-of select="$path" /></title>
</head>
<body>
<h1>
  <img src="/.logo.svg" width="40" height="48" alt="OpenWrt" />
  <xsl:text> Index of </xsl:text>
  <a href="/"><em>(root)</em></a>
  <xsl:text> / </xsl:text>
  <xsl:call-template name="breadcrumb">
    <xsl:with-param name="path" select="$path" />
  </xsl:call-template>
</h1>
<hr />

<!-- Device search: only on /targets/ pages, activated by search.js -->
<div id="device-search" class="ds" hidden="hidden">
  <input
                        id="ds-input"
                        type="search"
                        placeholder="Search devices&#x2026; e.g. Archer C7, Linksys, r7800"
                        autocomplete="off"
                    />
  <div id="ds-results" />
  <p id="ds-status" hidden="hidden" />
</div>

<table>
  <tr>
    <th class="n">File Name</th>
    <th class="s">File Size</th>
    <th class="d">Date</th>
  </tr>
  <xsl:apply-templates select="list/directory">
    <xsl:sort
                            select="."
                            data-type="text"
                            order="ascending"
                            case-order="lower-first"
                        />
  </xsl:apply-templates>
  <xsl:apply-templates select="list/file">
    <xsl:sort
                            select="."
                            data-type="text"
                            order="ascending"
                            case-order="lower-first"
                        />
  </xsl:apply-templates>
</table>

<footer>Open Source Downloads supported by
  <a href="https://www.fastly.com/">Fastly CDN</a>.</footer>

<script src="/.search.js" />

</body>
</html>
</xsl:template>

<!-- Breadcrumb: recursively split path into linked segments -->
<xsl:template name="breadcrumb">
  <xsl:param name="path" />
  <xsl:param name="built" select="'/'" />
  <!-- Strip leading slash -->
  <xsl:variable name="rest" select="substring-after($path, '/')" />
  <xsl:if test="string-length($rest) &gt; 0">
    <xsl:variable name="segment">
      <xsl:choose>
        <xsl:when test="contains($rest, '/')">
          <xsl:value-of select="substring-before($rest, '/')" />
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="$rest" />
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:if test="string-length($segment) &gt; 0">
      <xsl:variable name="href" select="concat($built, $segment, '/')" />
      <a href="{$href}"><xsl:value-of select="$segment" /></a>
      <xsl:text> / </xsl:text>
      <xsl:if test="contains($rest, '/')">
        <xsl:call-template name="breadcrumb">
          <xsl:with-param
                            name="path"
                            select="concat('/', substring-after($rest, '/'))"
                        />
          <xsl:with-param name="built" select="$href" />
        </xsl:call-template>
      </xsl:if>
    </xsl:if>
  </xsl:if>
</xsl:template>

<!-- Directory entry -->
<xsl:template match="directory">
  <tr>
    <td class="n">
      <a href="{.}/"><xsl:value-of select="." />/</a>
    </td>
    <td class="s">-</td>
    <td class="d">
      <xsl:value-of select="substring(@mtime, 1, 10)" />
      <xsl:text> </xsl:text>
      <xsl:value-of select="substring(@mtime, 12, 5)" />
    </td>
  </tr>
</xsl:template>

<!-- File entry -->
<xsl:template match="file">
  <tr>
    <td class="n">
      <a href="{.}"><xsl:value-of select="." /></a>
    </td>
    <td class="s">
      <xsl:call-template name="format-size">
        <xsl:with-param name="bytes" select="@size" />
      </xsl:call-template>
    </td>
    <td class="d">
      <xsl:value-of select="substring(@mtime, 1, 10)" />
      <xsl:text> </xsl:text>
      <xsl:value-of select="substring(@mtime, 12, 5)" />
    </td>
  </tr>
</xsl:template>

<!-- Format bytes into human-readable size -->
<xsl:template name="format-size">
  <xsl:param name="bytes" />
  <xsl:choose>
    <xsl:when test="$bytes &gt;= 1073741824">
      <xsl:value-of select="format-number($bytes div 1073741824, '0.0')" />
      <xsl:text> GB</xsl:text>
    </xsl:when>
    <xsl:when test="$bytes &gt;= 1048576">
      <xsl:value-of select="format-number($bytes div 1048576, '0.0')" />
      <xsl:text> MB</xsl:text>
    </xsl:when>
    <xsl:when test="$bytes &gt;= 1024">
      <xsl:value-of select="format-number($bytes div 1024, '0.0')" />
      <xsl:text> KB</xsl:text>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="$bytes" />
      <xsl:text> B</xsl:text>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

</xsl:stylesheet>
